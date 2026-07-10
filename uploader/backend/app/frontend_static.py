"""Optional built-in Vite frontend for single-host Docker deploy."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Paths that must never be handled by the SPA catch-all.
_RESERVED_TOP_LEVEL = frozenset({"health", "docs", "openapi.json", "redoc"})


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve a Vite ``dist/`` tree at ``/`` with SPA fallback."""
    static_dir = static_dir.resolve()
    index_path = static_dir / "index.html"
    if not index_path.is_file():
        raise RuntimeError(f"frontend static dir missing index.html: {static_dir}")

    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    async def spa_index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_fallback(spa_path: str) -> FileResponse:
        if spa_path.startswith("api/") or spa_path in _RESERVED_TOP_LEVEL:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = static_dir / spa_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)
