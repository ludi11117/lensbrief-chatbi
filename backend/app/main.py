import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from starlette.staticfiles import StaticFiles

from .api import catalog, files, identity, reports, workspaces
from .auth import Denied, audit
from .db import sqlite_engine
from .settings import Settings
from .storage import LocalStorage, ObjectStorage

def create_app(settings: Settings | None = None, storage: ObjectStorage | None = None):
    settings = settings or Settings.from_env()
    if settings.draft_mode not in {"mock", "llm"}:
        raise ValueError("LENSBRIEF_DRAFT_MODE must be mock or llm")
    if settings.planner_mode not in {"rules", "llm"}:
        raise ValueError("LENSBRIEF_PLANNER_MODE must be rules or llm")
    app = FastAPI(title="LensBrief ChatBI", version="1.0.0", docs_url=None,
                  redoc_url=None, openapi_url="/api/openapi.json", swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect")
    app.state.settings = settings
    app.state.engine = sqlite_engine(settings.database)
    app.state.session_factory = sessionmaker(bind=app.state.engine)
    app.state.storage = storage or LocalStorage(settings.files)

    for module in (identity, reports, files, catalog, workspaces):
        app.include_router(module.router, prefix="/api")

    @app.get("/api/docs", include_in_schema=False)
    def swagger():
        assets = "/assets/swagger-ui"
        return get_swagger_ui_html(
            openapi_url=app.openapi_url, title=f"{app.title} · API",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url=f"{assets}/swagger-ui-bundle.js", swagger_css_url=f"{assets}/swagger-ui.css",
            swagger_favicon_url=f"{assets}/favicon-32x32.png", swagger_ui_parameters={"validatorUrl": None},
        )

    @app.get("/api/docs/oauth2-redirect", include_in_schema=False)
    def swagger_redirect():
        return get_swagger_ui_oauth2_redirect_html()

    @app.get("/api/health", tags=["运行状态"])
    def health():
        with app.state.engine.connect() as connection:
            connection.execute(text("SELECT id FROM dataset LIMIT 1"))
        return {"status": "ok", "draft_mode": settings.draft_mode, "planner_mode": settings.planner_mode}

    @app.exception_handler(Denied)
    def forbidden(request: Request, exc: Denied):
        with request.app.state.session_factory.begin() as session:
            audit(session, exc.actor_id, "access.denied", exc.resource, exc.resource_id, permission=exc.action)
        return JSONResponse({"detail": "没有权限访问此资源或执行该操作。"}, status_code=403)

    frontend_dir = os.environ.get("LENSBRIEF_FRONTEND_DIST")
    if frontend_dir:
        frontend = Path(frontend_dir)
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="app-assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path == "api" or path.startswith("api/"):
                raise HTTPException(404, "接口不存在。")
            return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})

    return app
