"""FastAPI application: routes + wiring.

Run locally (standard dev port — see docs/LOCAL_DEV.md):
    uvicorn app.main:app --reload --port 8091

The module-level ``app`` is built from environment settings. Tests use the
``create_app(settings)`` factory to inject an isolated sandbox configuration.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pathlib import Path

from . import __version__
from .benchmark_store import BenchmarkStore, _default_yfinance_fetch
from .benchmarks import configure_store
from .config import Settings
from .db import Database, SchemaError
from .downstream_export import run_downstream_export
from .performance import build_combined, build_program
from .programs import (
    PROGRAM_LABELS,
    PROGRAMS,
    normalize_program,
    program_metadata,
    public_row,
)
from .security import require_actor
from .validation import RowValidationError, validate_row


def _resolve_program_or_404(program: str) -> str:
    code = normalize_program(program)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown program '{program}'. Valid: {', '.join(PROGRAMS)}.",
        )
    return code


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings()
    db = Database(settings.database_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            db.verify_schema()
        except SchemaError as exc:
            raise RuntimeError(str(exc)) from exc
        configure_store(
            BenchmarkStore(
                cache_dir=Path(settings.benchmark_cache_dir),
                cache_only=settings.benchmark_cache_only,
                allow_fixture=settings.benchmark_allow_fixture,
                fetcher=None if settings.benchmark_cache_only else _default_yfinance_fetch,
            )
        )
        yield

    app = FastAPI(
        title="Glenn Daily Uploader — Backend",
        version=__version__,
        description=(
            "Backend-only API for daily TKP/TCP/AGM/Y&Q value entry. "
            "Sandbox by default; export is dry-run only and never calls the "
            "four websites in this build."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Turn validation errors into a clean 422 with a per-field error map.
    @app.exception_handler(RowValidationError)
    async def _row_validation_handler(_request: Request, exc: RowValidationError):
        return JSONResponse(
            status_code=422,  # Unprocessable Content
            content={"detail": "validation_failed", "errors": exc.errors},
        )

    # -- meta -------------------------------------------------------------
    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {
            "status": "ok",
            "app_env": settings.app_env,
            "export_enabled": settings.export_enabled,
            "version": __version__,
        }

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "service": "glenn-daily-uploader-backend",
            "version": __version__,
            "app_env": settings.app_env,
            "docs": "/docs",
        }

    @app.get("/api/programs", tags=["programs"])
    def get_programs() -> dict:
        return {"programs": program_metadata()}

    @app.get("/api/performance", tags=["performance"])
    def get_performance(
        mode: str = Query(default="combined", pattern="^(combined|program)$"),
        program: Optional[str] = Query(default=None),
        benchmarks: Optional[str] = Query(
            default=None, description="Comma-separated symbols, e.g. SPX,NDX,BTC"
        ),
    ) -> dict:
        """Chart data for the performance card. Always computed fresh from the
        current `daily_rows` (no caching), so it reflects the latest add/delete/
        export immediately. See app/performance.py for the response contract.
        """
        if mode == "combined":
            return build_combined(db)

        code = normalize_program(program or "")
        if code is None:
            raise HTTPException(
                status_code=422,
                detail=f"program is required and must be one of {PROGRAMS} when mode=program",
            )

        bench_list: list[str] = []
        if benchmarks:
            seen: set[str] = set()
            for raw_sym in benchmarks.split(","):
                sym = raw_sym.strip().upper()
                if sym and sym not in seen:
                    seen.add(sym)
                    bench_list.append(sym)

        return build_program(db, code, bench_list)

    # -- rows -------------------------------------------------------------
    @app.get("/api/rows/{program}", tags=["rows"])
    def get_rows(program: str, limit: int = Query(default=7, ge=1, le=365)) -> dict:
        code = _resolve_program_or_404(program)
        rows = db.get_last_rows(code, limit)
        return {
            "program": code,
            "label": PROGRAM_LABELS[code],
            "count": len(rows),
            "rows": [public_row(code, r) for r in rows],
        }

    @app.post("/api/rows/{program}", tags=["rows"])
    def upsert_row(
        program: str,
        payload: dict[str, Any] = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict:
        code = _resolve_program_or_404(program)
        normalized = validate_row(code, payload)  # raises RowValidationError -> 422
        row, created = db.upsert_row(code, normalized, actor)
        return {
            "program": code,
            "created": created,
            "action": "create" if created else "update",
            "row": public_row(code, row),
        }

    @app.delete("/api/rows/{program}/last", tags=["rows"])
    def delete_last(
        program: str, actor: str = Depends(require_actor)
    ) -> dict:
        code = _resolve_program_or_404(program)
        deleted = db.delete_last_row(code, actor)
        if deleted is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No rows to delete for {code}.",
            )
        return {"program": code, "deleted": public_row(code, deleted)}

    # -- export -----------------------------------------------------------
    @app.post("/api/export/all", tags=["export"])
    def export_all(actor: str = Depends(require_actor)) -> dict:
        """Preview (and, when explicitly enabled, attempt) an export of all
        changed/unexported rows.

        SAFETY: this build never calls the TKP/TCP/AGM websites directly (Y&Q
        is never a target at all). In sandbox it is always a dry-run unless
        EXPORT_ENABLED=true. In production it is a dry-run unless
        EXPORT_ENABLED=true, but even then no external transport exists yet
        for the ORIGINAL uploader-only preview, so no request is made and no
        row is marked exported by that path alone.

        Downstream export (TKP/TCP/AGM sandbox destinations) is a SEPARATE,
        independently-flagged feature — see docs/downstream_export_contract.md.
        It only runs when EXPORT_DOWNSTREAM_ENABLED=true; when that flag is
        false (the default), this endpoint's behavior and response shape are
        UNCHANGED from before this feature existed.
        """
        rows = db.get_unexported_rows()

        programs_payload: dict[str, dict] = {}
        for code in PROGRAMS:
            code_rows = [public_row(code, r) for r in rows if r["program"] == code]
            programs_payload[code] = {
                "target_url": settings.export_url(code),  # future; not called
                "row_count": len(code_rows),
                "rows": code_rows,
            }

        would_export = settings.export_enabled and not settings.is_sandbox
        dry_run = not would_export

        batch_id = db.add_export_batch(
            app_env=settings.app_env,
            export_enabled=settings.export_enabled,
            dry_run=dry_run,
            row_count=len(rows),
            payload=programs_payload,
        )
        db.add_audit(
            action="export_dry_run" if dry_run else "export_enabled_noop",
            actor=actor,
            detail={"total_rows": len(rows), "batch_id": batch_id},
        )

        if dry_run:
            message = (
                "DRY RUN — preview only. No external calls were made and no "
                "rows were marked exported."
            )
        else:
            message = (
                "EXPORT_ENABLED is true, but external transport to the four "
                "websites is not implemented in this build. No external calls "
                "were made and no rows were marked exported."
            )

        response: dict = {
            "dry_run": dry_run,
            "app_env": settings.app_env,
            "export_enabled": settings.export_enabled,
            "transport_implemented": False,
            "external_calls_made": 0,
            "batch_id": batch_id,
            "total_rows": len(rows),
            "programs": programs_payload,
            "message": message,
        }

        if not settings.export_downstream_enabled:
            return response

        downstream_results = run_downstream_export(
            db=db,
            settings=settings,
            actor=actor,
            batch_id=batch_id,
            rows=rows,
        )
        response["downstream"] = {
            "target_env": settings.export_target_env,
            "dry_run": settings.export_dry_run,
            "results": downstream_results,
        }
        return response

    # -- audit ------------------------------------------------------------
    @app.get("/api/audit", tags=["audit"])
    def get_audit(limit: int = Query(default=50, ge=1, le=500)) -> dict:
        events = db.get_audit(limit)
        return {"count": len(events), "events": events}

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app()
