"""Reset the local sandbox SQLite database (sandbox / local dev only).

Creates a timestamped backup of the existing file before deleting it, then
initializes a fresh schema. Requires --confirm to run.

Usage (from backend/):
    python scripts/reset_local_db.py --confirm
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as `python scripts/reset_local_db.py` from backend/.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset local uploader SQLite DB")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required: acknowledge this deletes local sandbox data (after backup).",
    )
    args = parser.parse_args()
    if not args.confirm:
        print("Refusing to reset without --confirm.", file=sys.stderr)
        print("Example: python scripts/reset_local_db.py --confirm", file=sys.stderr)
        return 1

    settings = Settings()
    if settings.app_env != "sandbox":
        print(
            f"Refusing to reset while APP_ENV={settings.app_env!r}. "
            "Set APP_ENV=sandbox for local resets.",
            file=sys.stderr,
        )
        return 1

    db_path = Path(settings.database_path).expanduser()
    if db_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = db_path.with_suffix(db_path.suffix + f".bak.{stamp}")
        shutil.copy2(db_path, backup)
        print(f"Backed up existing DB to {backup}")
        db_path.unlink()
        journal = Path(str(db_path) + "-journal")
        if journal.exists():
            journal.unlink()

    Database(str(db_path))
    print(f"Initialized fresh database at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
