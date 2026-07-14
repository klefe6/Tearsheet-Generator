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
from .backfill import (
    backfill_disabled_detail,
    run_backfill_import,
    run_source_preview,
    sandbox_only_detail,
)
from .benchmark_store import BenchmarkStore, _default_yfinance_fetch
from .benchmarks import configure_store
from . import rollback as rollback_mod
from .config import Settings
from .db import (
    BATCH_COMMITTED,
    BATCH_DRY_RUN,
    BATCH_LEGACY,
    BATCH_NO_MUTATION,
    BATCH_PARTIALLY_FAILED,
    Database,
    SchemaError,
)
from .downstream_export import run_downstream_export
from .frontend_static import mount_frontend
from .performance import build_combined, build_program
from .programs import (
    PROGRAM_FIELDS,
    PROGRAM_LABELS,
    PROGRAMS,
    normalize_program,
    program_metadata,
    program_nlv,
    public_row,
)
from .security import require_actor, require_admin_actor
from .trading_calendar import get_trading_date_status
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
            "serve_frontend": settings.serve_frontend,
        }

    if not settings.serve_frontend:

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

    @app.get("/api/trading-date-status", tags=["meta"])
    def trading_date_status() -> dict:
        """Authoritative NYSE session dates for the uploader UI (America/New_York)."""
        return get_trading_date_status()

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
        """Glenn's MANUAL entries only (daily_rows) — export/audit semantics.
        Backfilled history is never returned here; the bottom tables use
        GET /api/display-rows/{program} instead."""
        code = _resolve_program_or_404(program)
        rows = db.get_last_rows(code, limit)
        exclusions = db.get_active_exclusions_map()
        return {
            "program": code,
            "label": PROGRAM_LABELS[code],
            "count": len(rows),
            "rows": [
                public_row(
                    code,
                    r,
                    exclusion=exclusions.get((code, int(r["id"]))),
                )
                for r in rows
            ],
        }

    @app.get("/api/display-rows/{program}", tags=["rows"])
    def get_display_rows(
        program: str, limit: int = Query(default=7, ge=1, le=60)
    ) -> dict:
        """Latest merged values for the bottom tables — DISPLAY ONLY.

        Includes backfilled historical rows, labeled per row via
        ``row_source`` / ``source_label``, so Glenn sees the latest known
        values. A manual entry always supersedes a historical row on the same
        date. Export semantics are untouched: /api/export/all reads only
        daily_rows, and GET /api/rows/{program} stays manual-only.

        Each row carries ``value`` — the same program value the performance
        graph uses (``program_nlv``): TKP equity-curve NAV for backfilled
        rows (StoneX+Plus500 for manual ones), TCP nav-x1, AGM TradeStation
        NLV. AGM ``fee`` is reported only on manual rows — the historical
        source never provided one, so none is invented.
        """
        code = _resolve_program_or_404(program)
        exclusions = db.get_active_exclusions_map()
        # Map date -> daily_rows id for manual rows so we can attach export_state.
        manual_by_date = {
            r["date"]: r for r in db.get_last_rows(code, limit=max(limit, 60))
        }
        out = []
        for r in db.get_display_rows(code, limit):
            manual = r.get("row_source") == "manual"
            item: dict[str, Any] = {
                "date": r["date"],
                "value": program_nlv(code, r),
                "row_source": r.get("row_source"),
                "source_label": "Manual" if manual else "Backfilled",
            }
            for f in PROGRAM_FIELDS[code]:
                if f.name == "date":
                    continue
                value = r.get(f.name)
                if f.name == "fee" and not manual:
                    value = None  # never invent a historical fee
                item[f.name] = value
            if not manual and r.get("source_detail"):
                item["source_detail"] = r["source_detail"]
            if manual:
                raw = manual_by_date.get(r["date"])
                if raw is not None:
                    excl = exclusions.get((code, int(raw["id"])))
                    projected = public_row(code, raw, exclusion=excl)
                    item["id"] = projected.get("id")
                    item["exported"] = projected["exported"]
                    item["export_state"] = projected["export_state"]
                    item["excluded"] = projected["excluded"]
                    item["excluded_reason"] = projected["excluded_reason"]
            out.append(item)

        resp: dict[str, Any] = {
            "program": code,
            "label": PROGRAM_LABELS[code],
            "count": len(out),
            "rows": out,
            "display_note": (
                "Latest values include historical backfill where available."
            ),
            "export_note": (
                "Export All only includes rows manually entered in the uploader."
            ),
        }
        if code == "YQ" and not out:
            resp["empty_reason"] = "No daily Y&Q source available."
        return resp

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
        counts = db.export_row_counts()
        exclusions = db.get_active_exclusions_map()

        programs_payload: dict[str, dict] = {}
        for code in PROGRAMS:
            code_rows = [
                public_row(
                    code,
                    r,
                    exclusion=exclusions.get((code, int(r["id"]))),
                )
                for r in rows
                if r["program"] == code
            ]
            programs_payload[code] = {
                "target_url": settings.export_url(code),  # future; not called
                "row_count": len(code_rows),
                "rows": code_rows,
            }

        would_export = settings.export_enabled and not settings.is_sandbox
        dry_run = not would_export

        # A batch only becomes a rollback candidate if it actually commits a
        # downstream write; anything else is recorded with a status that keeps
        # it out of "roll back the last export" by construction.
        will_mutate_downstream = (
            settings.export_downstream_enabled and not settings.export_dry_run
        )
        batch_id = db.add_export_batch(
            app_env=settings.app_env,
            export_enabled=settings.export_enabled,
            dry_run=dry_run,
            row_count=len(rows),
            payload=programs_payload,
            # Provisional and deliberately un-reversible. Promoted to
            # committed/partially_failed below ONLY if a real write lands.
            status=BATCH_DRY_RUN if settings.export_dry_run else BATCH_NO_MUTATION,
            actor=actor,
            target_env=settings.export_target_env,
            downstream_enabled=settings.export_downstream_enabled,
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
            "eligible_count": counts["eligible"],
            "excluded_count": counts["excluded"],
            "exported_count": counts["exported"],
            "manual_total": counts["manual_total"],
            "programs": programs_payload,
            "message": message,
        }

        if not settings.export_downstream_enabled:
            return response

        # A real downstream write takes the same lock a rollback takes, so an
        # export can never interleave with a rollback of an earlier batch.
        if will_mutate_downstream and not db.acquire_lock(f"export:{actor}"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An export or rollback is already in progress; try again shortly.",
            )
        try:
            downstream_results, external_calls = run_downstream_export(
                db=db,
                settings=settings,
                actor=actor,
                batch_id=batch_id,
                rows=rows,
            )
        finally:
            if will_mutate_downstream:
                db.release_lock()

        if will_mutate_downstream:
            statuses = {
                r["status"]
                for prog in downstream_results.values()
                for r in prog["date_results"]
            }
            if "success" in statuses:
                db.set_batch_status(
                    batch_id,
                    BATCH_PARTIALLY_FAILED if "failure" in statuses else BATCH_COMMITTED,
                )
            else:
                db.set_batch_status(batch_id, BATCH_NO_MUTATION)

        response["downstream"] = {
            "target_env": settings.export_target_env,
            "dry_run": settings.export_dry_run,
            "results": downstream_results,
        }
        # The real tearsheet-ingest transport exists for target "production";
        # these fields now report what actually happened this batch.
        if settings.export_target_env == "production":
            response["transport_implemented"] = True
        response["external_calls_made"] = external_calls
        return response

    @app.get("/api/export/eligibility", tags=["export"])
    def export_eligibility() -> dict:
        """Manual-row tallies for the export summary strip (read-only)."""
        counts = db.export_row_counts()
        return {
            "manual_total": counts["manual_total"],
            "exported": counts["exported"],
            "excluded": counts["excluded"],
            "eligible": counts["eligible"],
        }

    @app.post("/api/export/exclusions", tags=["export"])
    def create_export_exclusion(
        payload: dict[str, Any] = Body(...),
        actor: str = Depends(require_admin_actor),
    ) -> dict:
        """Exclude one daily_rows record from Export All without marking it exported."""
        program = normalize_program(str(payload.get("program", "")))
        if program is None:
            raise HTTPException(status_code=404, detail="Unknown program")
        try:
            source_row_id = int(payload["source_row_id"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(
                status_code=422, detail="'source_row_id' must be an integer"
            )
        reason = str(payload.get("reason") or "").strip()
        if not reason:
            raise HTTPException(status_code=422, detail="'reason' is required")

        row = db.get_daily_row_by_id(program, source_row_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Row not found")
        if bool(row.get("exported", 0)):
            raise HTTPException(
                status_code=409,
                detail="Cannot exclude an already-exported row",
            )

        exclusion = db.add_export_exclusion(program, source_row_id, reason, actor)
        db.add_audit(
            action="export_exclusion_created",
            actor=actor,
            program=program,
            date=row["date"],
            detail={
                "source_row_id": source_row_id,
                "exclusion_id": exclusion["id"],
                "reason": reason,
            },
        )
        return {
            "ok": True,
            "exclusion": dict(exclusion),
            "row": public_row(program, row, exclusion=exclusion),
        }

    @app.delete(
        "/api/export/exclusions/{program}/{source_row_id}",
        tags=["export"],
    )
    def restore_export_exclusion(
        program: str,
        source_row_id: int,
        actor: str = Depends(require_admin_actor),
    ) -> dict:
        """Restore an excluded row to the export queue (deactivate exclusion)."""
        code = _resolve_program_or_404(program)
        row = db.get_daily_row_by_id(code, source_row_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Row not found")
        removed = db.remove_export_exclusion(code, source_row_id, actor)
        if removed is None:
            raise HTTPException(status_code=404, detail="No active exclusion")
        db.add_audit(
            action="export_exclusion_removed",
            actor=actor,
            program=code,
            date=row["date"],
            detail={
                "source_row_id": source_row_id,
                "exclusion_id": removed["id"],
                "reason": removed.get("reason"),
            },
        )
        return {
            "ok": True,
            "exclusion": removed,
            "row": public_row(code, row, exclusion=None),
        }

    # -- export rollback ---------------------------------------------------
    # Reverses the most recent COMMITTED downstream batch. Always requires a
    # valid ADMIN_API_TOKEN (require_admin_actor), in every environment.
    def _blocked(exc: rollback_mod.RollbackBlocked, batch_id: Optional[int] = None) -> JSONResponse:
        """A blocked rollback is a 200 with reversible:false, not an error — the
        UI needs to render the reasons, and 'you cannot roll this back' is a
        successful answer to 'can I roll this back?'."""
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ok": True,
                "reversible": False,
                "batch_id": batch_id,
                "programs": [],
                "blocking_reasons": exc.reasons,
                "warnings": [],
                "confirmation_token": None,
                "expires_at": None,
            },
        )

    @app.get("/api/export/rollback/capability", tags=["export"])
    def rollback_capability() -> dict:
        """Unauthenticated capability probe so the UI can hide/disable the button."""
        return rollback_mod.capability(settings)

    @app.post("/api/export/batches/latest/rollback/preview", tags=["export"])
    def rollback_preview_latest(actor: str = Depends(require_admin_actor)) -> Any:
        try:
            return rollback_mod.preview(db, settings, actor)
        except rollback_mod.RollbackBlocked as exc:
            return _blocked(exc)

    @app.post("/api/export/batches/{batch_id}/rollback/preview", tags=["export"])
    def rollback_preview_batch(
        batch_id: int, actor: str = Depends(require_admin_actor)
    ) -> Any:
        try:
            return rollback_mod.preview(db, settings, actor, batch_id=batch_id)
        except rollback_mod.RollbackBlocked as exc:
            return _blocked(exc, batch_id)

    @app.post("/api/export/batches/{batch_id}/rollback/confirm", tags=["export"])
    def rollback_confirm(
        batch_id: int,
        payload: dict = Body(...),
        actor: str = Depends(require_admin_actor),
    ) -> Any:
        try:
            return rollback_mod.confirm(
                db,
                settings,
                actor,
                batch_id,
                confirmation_token=str(payload.get("confirmation_token") or ""),
                reason=str(payload.get("reason") or ""),
            )
        except rollback_mod.RollbackBlocked as exc:
            # A refused EXECUTION is a 409 — unlike preview, the caller asked us
            # to mutate and we did not.
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "ok": False,
                    "batch_id": batch_id,
                    "status": "blocked",
                    "blocking_reasons": exc.reasons,
                },
            )

    # -- historical backfill (sandbox-only, BACKFILL_ENABLED-gated) ---------
    def _require_backfill_enabled() -> None:
        """All /api/backfill/* endpoints: sandbox-only AND BACKFILL_ENABLED.

        Production refuses regardless of the flag (no override exists);
        sandbox additionally requires the explicit opt-in so a deployed
        sandbox has no live backfill surface until an operator turns it on.
        """
        if not settings.is_sandbox:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=sandbox_only_detail()
            )
        if not settings.backfill_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=backfill_disabled_detail()
            )

    @app.get("/api/backfill/preview", tags=["backfill"])
    def backfill_preview(actor: str = Depends(require_actor)) -> dict:
        """READ-ONLY dry-run preview straight from the tearsheet source files.

        Only useful on a host that has the tearsheet files and the extractor
        (the ops machine, with BACKFILL_SOURCE_REPO_ROOT set); the deployed
        sandbox reports sources unavailable and points at the offline
        extractor + POST /api/backfill/import flow. Writes nothing anywhere.
        """
        _require_backfill_enabled()
        return run_source_preview(db, settings, actor)

    @app.post("/api/backfill/import", tags=["backfill"])
    def backfill_import(
        payload: dict[str, Any] = Body(...),
        actor: str = Depends(require_actor),
    ) -> dict:
        """Import extracted tearsheet history into `historical_rows`.

        SANDBOX ONLY and gated on BACKFILL_ENABLED — 403 otherwise; there is
        no production override. Body: {"dry_run": bool (default true),
        "rows": [{program, date, <program fields>, source, source_detail?},
        ...]}. Dry-run classifies every row through the same code path as a
        real import but writes nothing. Never touches daily_rows, never calls
        or writes any tearsheet app — see docs/historical_backfill.md.
        """
        _require_backfill_enabled()
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise HTTPException(status_code=422, detail="'rows' must be a JSON array")
        dry_run = payload.get("dry_run", True)
        if not isinstance(dry_run, bool):
            raise HTTPException(status_code=422, detail="'dry_run' must be a boolean")
        return run_backfill_import(db, settings, actor, rows, dry_run)

    @app.get("/api/backfill/status", tags=["backfill"])
    def backfill_status() -> dict:
        """Per-program audit view of backfilled history currently stored."""
        _require_backfill_enabled()
        return {
            "app_env": settings.app_env,
            "programs": db.historical_summary(),
            "precedence": (
                "Manual daily_rows entries always supersede historical rows on "
                "the same (program, date)."
            ),
        }

    @app.delete("/api/backfill", tags=["backfill"])
    def backfill_clear(
        program: Optional[str] = Query(default=None),
        actor: str = Depends(require_actor),
    ) -> dict:
        """Remove backfilled rows (all, or ?program=TKP). Reversibility hatch:
        only `historical_rows` is cleared; Glenn's daily_rows are untouched.
        """
        _require_backfill_enabled()
        code: Optional[str] = None
        if program is not None:
            code = _resolve_program_or_404(program)
        deleted = db.clear_historical_rows(actor=actor, program=code)
        return {"deleted": deleted, "program": code}

    # -- audit ------------------------------------------------------------
    @app.get("/api/audit", tags=["audit"])
    def get_audit(limit: int = Query(default=50, ge=1, le=500)) -> dict:
        events = db.get_audit(limit)
        return {"count": len(events), "events": events}

    if settings.serve_frontend:
        static_dir = Path(settings.frontend_static_dir)
        mount_frontend(app, static_dir)

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app()
