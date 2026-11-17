"""FastAPI application factory."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from backend.db.session import ROOT, Database
from backend.errors import install_error_handlers
from backend.middleware import RequestLogMiddleware
from backend.routers import admin, cron, library, public
from backend.services.hub import ServiceHub
from snap2cook.config import Settings


def create_app(settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    """Build the app. ``settings``/``db`` can be injected (tests); otherwise they come from the environment."""
    settings = settings or Settings.load()
    app = FastAPI(title="Snap2Cook API", version=public.VERSION, docs_url="/api/docs" if settings.env == "dev" else None,
                  redoc_url=None, openapi_url="/api/openapi.json" if settings.env == "dev" else None)
    app.state.hub = ServiceHub(settings, db)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["x-request-id", "retry-after"])
    app.add_middleware(RequestLogMiddleware, hub=app.state.hub)
    install_error_handlers(app)
    for module in (public, library, admin, cron):
        app.include_router(module.router)
    _serve_built_frontend(app)
    return app


def _serve_built_frontend(app: FastAPI) -> None:
    """Local/self-hosted convenience: serve ``frontend/dist`` (on Vercel the CDN serves it, so this is skipped)."""
    dist = ROOT / "frontend" / "dist"
    if os.environ.get("VERCEL") or not (dist / "index.html").is_file():
        return

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        target = (dist / path).resolve()
        inside = dist.resolve() in target.parents
        return FileResponse(target if inside and target.is_file() else dist / "index.html")


app = create_app()
