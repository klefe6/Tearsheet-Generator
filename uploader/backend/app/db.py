"""SQLite storage layer.

A thin, dependency-free repository built on the standard-library ``sqlite3``
module. Tables:

  * daily_rows       — one row per (program, date); idempotent upsert. Only
                       Glenn's manual entries live here.
  * historical_rows  — one row per (program, date) imported from tearsheet
                       history (backfill). NEVER written by the manual entry
                       path and NEVER read by the export path; merged with
                       daily_rows for the performance chart only, where a
                       manual daily_row always wins on a date collision.
  * audit_events     — append-only log of create/update/delete/export actions.
  * export_batches   — a saved snapshot of each export preview (dry-run record).
  * backfill_batches — a saved snapshot of each backfill import (incl. dry-runs).

A fresh connection is opened per operation (simple and thread-safe for the
low write volume of a daily uploader). Use a real file path for persistence;
``:memory:`` will not persist across operations.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .programs import DATA_COLUMNS

# Tables and columns the running app requires. Used by verify_schema() so a
# stale/partial SQLite file (e.g. from an older build) fails fast with a
# clear message instead of opaque 500s on row/performance routes.
_REQUIRED_SCHEMA: dict[str, set[str]] = {
    "daily_rows": {
        "id",
        "program",
        "date",
        "stonex_nlv",
        "plus500_nlv",
        "tradestation_nlv",
        "cash_transfer",
        "fee",
        "exported",
        "created_at",
        "updated_at",
    },
    "historical_rows": {
        "id",
        "program",
        "date",
        "stonex_nlv",
        "plus500_nlv",
        "tradestation_nlv",
        "cash_transfer",
        "fee",
        "source",
        "source_detail",
        "batch_id",
        "imported_at",
        "updated_at",
    },
    "audit_events": {"id", "ts", "action", "program", "date", "detail", "actor"},
    "export_batches": {
        "id",
        "ts",
        "app_env",
        "export_enabled",
        "dry_run",
        "row_count",
        "payload",
    },
    "backfill_batches": {
        "id",
        "ts",
        "app_env",
        "dry_run",
        "actor",
        "row_count",
        "summary",
    },
}


class SchemaError(RuntimeError):
    """Raised when the SQLite file exists but does not match the expected schema."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_rows (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    program           TEXT    NOT NULL,
    date              TEXT    NOT NULL,
    stonex_nlv        REAL,
    plus500_nlv       REAL,
    tradestation_nlv  REAL,
    cash_transfer     REAL    NOT NULL DEFAULT 0,
    fee               REAL,
    exported          INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL,
    UNIQUE (program, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_rows_program_date
    ON daily_rows (program, date);

CREATE TABLE IF NOT EXISTS historical_rows (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    program           TEXT    NOT NULL,
    date              TEXT    NOT NULL,
    stonex_nlv        REAL,
    plus500_nlv       REAL,
    tradestation_nlv  REAL,
    cash_transfer     REAL    NOT NULL DEFAULT 0,
    fee               REAL,
    source            TEXT    NOT NULL,
    source_detail     TEXT,
    batch_id          INTEGER,
    imported_at       TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL,
    UNIQUE (program, date)
);

CREATE INDEX IF NOT EXISTS idx_historical_rows_program_date
    ON historical_rows (program, date);

CREATE TABLE IF NOT EXISTS backfill_batches (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT    NOT NULL,
    app_env   TEXT    NOT NULL,
    dry_run   INTEGER NOT NULL,
    actor     TEXT    NOT NULL,
    row_count INTEGER NOT NULL,
    summary   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    action   TEXT NOT NULL,
    program  TEXT,
    date     TEXT,
    detail   TEXT,
    actor    TEXT
);

CREATE TABLE IF NOT EXISTS export_batches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT    NOT NULL,
    app_env        TEXT    NOT NULL,
    export_enabled INTEGER NOT NULL,
    dry_run        INTEGER NOT NULL,
    row_count      INTEGER NOT NULL,
    payload        TEXT    NOT NULL
);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            parent = Path(path).expanduser().parent
            if str(parent) and not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    def verify_schema(self) -> None:
        """Ensure every required table exists with the expected columns.

        Raises SchemaError with an actionable message when the on-disk file is
        from an older build or is corrupt — the usual cause of /api/rows/*
        returning 500 while /health still returns 200.
        """
        if self.path == ":memory:":
            return

        db_file = Path(self.path).expanduser()
        if not db_file.exists():
            return  # init_schema() will create a fresh file on first write

        with self.connect() as conn:
            for table, required_cols in _REQUIRED_SCHEMA.items():
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if row is None:
                    raise SchemaError(
                        f"SQLite database at {db_file} is missing table '{table}'. "
                        "Run: python scripts/reset_local_db.py --confirm"
                    )
                actual = {
                    r["name"]
                    for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
                }
                missing = required_cols - actual
                if missing:
                    raise SchemaError(
                        f"SQLite database at {db_file} has outdated schema on "
                        f"'{table}' (missing columns: {sorted(missing)}). "
                        "Run: python scripts/reset_local_db.py --confirm"
                    )

    # --- daily_rows -------------------------------------------------------
    def upsert_row(self, program: str, data: dict, actor: str) -> tuple[dict, bool]:
        """Insert or update the row for (program, data['date']).

        Returns (stored_row, created). Any write resets ``exported`` to 0 so a
        changed value is re-included in the next export preview. Records a
        create/update audit event.
        """
        now = _utcnow()
        values = {col: data.get(col) for col in DATA_COLUMNS}
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM daily_rows WHERE program = ? AND date = ?",
                (program, data["date"]),
            ).fetchone()
            created = existing is None

            if created:
                cols = ", ".join(DATA_COLUMNS)
                placeholders = ", ".join(["?"] * len(DATA_COLUMNS))
                conn.execute(
                    f"INSERT INTO daily_rows "
                    f"(program, date, {cols}, exported, created_at, updated_at) "
                    f"VALUES (?, ?, {placeholders}, 0, ?, ?)",
                    (
                        program,
                        data["date"],
                        *[values[c] for c in DATA_COLUMNS],
                        now,
                        now,
                    ),
                )
            else:
                set_clause = ", ".join(f"{c} = ?" for c in DATA_COLUMNS)
                conn.execute(
                    f"UPDATE daily_rows SET {set_clause}, exported = 0, updated_at = ? "
                    f"WHERE program = ? AND date = ?",
                    (*[values[c] for c in DATA_COLUMNS], now, program, data["date"]),
                )

            row = conn.execute(
                "SELECT * FROM daily_rows WHERE program = ? AND date = ?",
                (program, data["date"]),
            ).fetchone()

            conn.execute(
                "INSERT INTO audit_events (ts, action, program, date, detail, actor) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    now,
                    "create" if created else "update",
                    program,
                    data["date"],
                    json.dumps(values),
                    actor,
                ),
            )
        return dict(row), created

    def get_last_rows(self, program: str, limit: int = 7) -> list[dict]:
        """Return the most recent `limit` rows for `program` (newest first)."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_rows WHERE program = ? "
                "ORDER BY date DESC, id DESC LIMIT ?",
                (program, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_rows(self, program: str) -> list[dict]:
        """Return every stored row for `program`, oldest first (date ascending).

        Used by the performance builder, which needs the full history to
        compound a normalized series — unlike `get_last_rows`, nothing is
        truncated here.
        """
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_rows WHERE program = ? ORDER BY date ASC, id ASC",
                (program,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_last_row(self, program: str, actor: str) -> Optional[dict]:
        """Delete the newest row for `program`. Returns it, or None if empty."""
        now = _utcnow()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_rows WHERE program = ? "
                "ORDER BY date DESC, id DESC LIMIT 1",
                (program,),
            ).fetchone()
            if row is None:
                return None
            conn.execute("DELETE FROM daily_rows WHERE id = ?", (row["id"],))
            conn.execute(
                "INSERT INTO audit_events (ts, action, program, date, detail, actor) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, "delete", program, row["date"], json.dumps(dict(row)), actor),
            )
        return dict(row)

    def get_unexported_rows(self) -> list[dict]:
        """All rows not yet marked exported (i.e. changed/new), ordered."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_rows WHERE exported = 0 ORDER BY program, date"
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_exported(self, program: str, date: str) -> None:
        """Flip `exported` to 1 for one (program, date) row.

        Called ONLY after a downstream export attempt for that row succeeds —
        a failed or skipped row is deliberately left `exported=0` so the next
        export batch naturally retries it (it stays in get_unexported_rows()).
        """
        with self.connect() as conn:
            conn.execute(
                "UPDATE daily_rows SET exported = 1 WHERE program = ? AND date = ?",
                (program, date),
            )

    # --- historical (backfill) rows ----------------------------------------
    def upsert_historical_row(
        self,
        program: str,
        data: dict,
        source: str,
        source_detail: Optional[str],
        batch_id: Optional[int],
        dry_run: bool = False,
    ) -> str:
        """Insert or update the historical row for (program, data['date']).

        Returns one of "created" / "updated" / "unchanged" so the import can
        prove idempotency (a re-import of identical data reports every row
        "unchanged" and rewrites nothing). With ``dry_run=True`` the action is
        classified through the exact same logic but nothing is written — a
        dry-run preview is therefore guaranteed to match the real import that
        follows it. Never touches daily_rows.
        """
        now = _utcnow()
        values = {col: data.get(col) for col in DATA_COLUMNS}
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT * FROM historical_rows WHERE program = ? AND date = ?",
                (program, data["date"]),
            ).fetchone()

            if existing is None:
                if dry_run:
                    return "created"
                cols = ", ".join(DATA_COLUMNS)
                placeholders = ", ".join(["?"] * len(DATA_COLUMNS))
                conn.execute(
                    f"INSERT INTO historical_rows "
                    f"(program, date, {cols}, source, source_detail, batch_id, "
                    f"imported_at, updated_at) "
                    f"VALUES (?, ?, {placeholders}, ?, ?, ?, ?, ?)",
                    (
                        program,
                        data["date"],
                        *[values[c] for c in DATA_COLUMNS],
                        source,
                        source_detail,
                        batch_id,
                        now,
                        now,
                    ),
                )
                return "created"

            same_values = all(
                existing[c] == values[c]
                or (existing[c] is not None and values[c] is not None
                    and float(existing[c]) == float(values[c]))
                for c in DATA_COLUMNS
            )
            if same_values and existing["source"] == source:
                return "unchanged"

            if dry_run:
                return "updated"

            set_clause = ", ".join(f"{c} = ?" for c in DATA_COLUMNS)
            conn.execute(
                f"UPDATE historical_rows SET {set_clause}, source = ?, "
                f"source_detail = ?, batch_id = ?, updated_at = ? "
                f"WHERE program = ? AND date = ?",
                (
                    *[values[c] for c in DATA_COLUMNS],
                    source,
                    source_detail,
                    batch_id,
                    now,
                    program,
                    data["date"],
                ),
            )
            return "updated"

    def get_historical_rows(self, program: str) -> list[dict]:
        """Every historical (backfilled) row for `program`, oldest first."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM historical_rows WHERE program = ? "
                "ORDER BY date ASC, id ASC",
                (program,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_merged_rows(self, program: str) -> list[dict]:
        """Historical + manual rows for `program`, oldest first.

        Precedence (explicit design, see docs/historical_backfill.md): a manual
        daily_rows entry ALWAYS wins over a historical row on the same date —
        Glenn's entries supersede imported history, never the other way round.
        Each returned row carries `row_source`: "manual" for daily_rows, or the
        import's source label (e.g. "tkp_state_json") for historical rows.
        """
        manual = self.get_all_rows(program)
        manual_dates = {r["date"] for r in manual}
        merged = []
        for r in manual:
            r = dict(r)
            r["row_source"] = "manual"
            merged.append(r)
        for r in self.get_historical_rows(program):
            if r["date"] in manual_dates:
                continue
            r = dict(r)
            r["row_source"] = r.get("source") or "backfill"
            merged.append(r)
        merged.sort(key=lambda r: r["date"])
        return merged

    def historical_summary(self) -> dict[str, dict]:
        """Per-program audit view of what has been backfilled."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT program, COUNT(*) AS n, MIN(date) AS first_date, "
                "MAX(date) AS last_date, MAX(imported_at) AS last_imported_at "
                "FROM historical_rows GROUP BY program"
            ).fetchall()
            sources = conn.execute(
                "SELECT program, source, COUNT(*) AS n FROM historical_rows "
                "GROUP BY program, source"
            ).fetchall()
        out: dict[str, dict] = {}
        for r in rows:
            out[r["program"]] = {
                "row_count": r["n"],
                "first_date": r["first_date"],
                "last_date": r["last_date"],
                "last_imported_at": r["last_imported_at"],
                "sources": {},
            }
        for s in sources:
            out[s["program"]]["sources"][s["source"]] = s["n"]
        return out

    def clear_historical_rows(self, actor: str, program: Optional[str] = None) -> int:
        """Delete backfilled rows (all, or one program's). Reversibility hatch:
        removes ONLY historical_rows — Glenn's daily_rows are never touched.
        Returns the number of rows deleted and records an audit event.
        """
        with self.connect() as conn:
            if program is None:
                cur = conn.execute("DELETE FROM historical_rows")
            else:
                cur = conn.execute(
                    "DELETE FROM historical_rows WHERE program = ?", (program,)
                )
            deleted = cur.rowcount
            conn.execute(
                "INSERT INTO audit_events (ts, action, program, date, detail, actor) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _utcnow(),
                    "backfill_clear",
                    program,
                    None,
                    json.dumps({"deleted": deleted}),
                    actor,
                ),
            )
        return deleted

    # --- backfill batches ---------------------------------------------------
    def add_backfill_batch(
        self,
        app_env: str,
        dry_run: bool,
        actor: str,
        row_count: int,
        summary: Any,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO backfill_batches "
                "(ts, app_env, dry_run, actor, row_count, summary) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _utcnow(),
                    app_env,
                    int(dry_run),
                    actor,
                    row_count,
                    json.dumps(summary),
                ),
            )
            return int(cur.lastrowid)

    # --- audit ------------------------------------------------------------
    def add_audit(
        self,
        action: str,
        actor: str,
        program: Optional[str] = None,
        date: Optional[str] = None,
        detail: Optional[dict] = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO audit_events (ts, action, program, date, detail, actor) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _utcnow(),
                    action,
                    program,
                    date,
                    json.dumps(detail) if detail is not None else None,
                    actor,
                ),
            )
            return int(cur.lastrowid)

    def get_last_activity_ts(self) -> Optional[str]:
        """Timestamp of the most recent audit event, or None if there are none.

        Every row create/update/delete and every export preview writes an audit
        event, so this single query is a correct "last changed" signal for the
        performance endpoint without needing a separate cache/version column.
        """
        with self.connect() as conn:
            row = conn.execute("SELECT MAX(ts) AS ts FROM audit_events").fetchone()
        return row["ts"] if row and row["ts"] else None

    def get_audit(self, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("detail"):
                try:
                    d["detail"] = json.loads(d["detail"])
                except (ValueError, TypeError):
                    pass
            out.append(d)
        return out

    # --- export batches ---------------------------------------------------
    def add_export_batch(
        self,
        app_env: str,
        export_enabled: bool,
        dry_run: bool,
        row_count: int,
        payload: Any,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO export_batches "
                "(ts, app_env, export_enabled, dry_run, row_count, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _utcnow(),
                    app_env,
                    int(export_enabled),
                    int(dry_run),
                    row_count,
                    json.dumps(payload),
                ),
            )
            return int(cur.lastrowid)
