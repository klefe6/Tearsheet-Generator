"""SQLite storage layer.

A thin, dependency-free repository built on the standard-library ``sqlite3``
module. Tables:

  * daily_rows      — one row per (program, date); idempotent upsert.
  * audit_events    — append-only log of create/update/delete/export actions.
  * export_batches  — a saved snapshot of each export preview (dry-run record).

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
