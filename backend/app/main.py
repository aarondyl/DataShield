"""FastAPI 应用入口：CORS、路由注册、启动时建表 + 种子数据 + 向量索引重建。

本地开发启动::

    DATABASE_URL=sqlite:///./datashield.db LLM_PROVIDER=mock EMBEDDING_PROVIDER=local \
        uvicorn app.main:app --reload

Docker/PostgreSQL 部署时先执行 ``alembic upgrade head`` 再启动（见 Dockerfile）。
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.db.session import SessionLocal, init_db, init_regintel_db, is_sqlite


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """启动流程：建表 → （SQLite）重建本地向量索引 → 写种子数据（仅当库为空）。"""
    settings = get_settings()
    if settings.runtime_mode == "cloud":
        init_regintel_db()
    else:
        init_db()
    if is_sqlite() and settings.runtime_mode != "cloud":
        from app.rag.retrieval import rebuild_local_store_from_db
        from app.regintel.retrieval import rebuild_legal_chunk_store_from_db
        # 覆盖重启场景：把库里已有的条款向量重新加载进内存索引
        rebuild_local_store_from_db()
        rebuild_legal_chunk_store_from_db()
    if settings.run_seed and settings.runtime_mode != "cloud":
        from app.services.seed import seed_if_empty
        with SessionLocal() as db:
            seed_if_empty(db)
    # 可选：法规来源定时轮询（SCHEDULER_ENABLED=true 时启动）
    if settings.runtime_mode == "cloud":
        from app.services.scheduler import start_scheduler
        scheduler = start_scheduler()
    else:
        scheduler = None
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    """按运行模式装载路由；云端法规进程不暴露私有业务 API。"""
    app = FastAPI(title="DataShield API", version="3.0.0", lifespan=lifespan)
    mode = get_settings().runtime_mode
    from app.api import health
    app.include_router(health.router, prefix="/api")
    if mode == "cloud":
        from app.api import regintel
        app.include_router(regintel.router, prefix="/api")
        return app
    from app.api import actions, analysis, companies, compliance, developer, evaluation, feedback, findings, local_regulations, products, regulations, remediations, tenant_agent, today, ui_understanding
    for module in (companies, products, regulations, analysis, actions, compliance, developer):
        app.include_router(module.router, prefix="/api")
    if mode == "web":
        from app.api import regintel
        app.include_router(regintel.router, prefix="/api")
    for module in (evaluation, tenant_agent, findings, remediations, feedback, today, ui_understanding, local_regulations):
        app.include_router(module.router, prefix="/api")
    from app.api import product_twin, repository_understanding, website_understanding
    app.include_router(website_understanding.router)
    app.include_router(website_understanding.router, prefix="/api", include_in_schema=False)
    app.include_router(repository_understanding.router)
    app.include_router(repository_understanding.router, prefix="/api", include_in_schema=False)
    app.include_router(product_twin.router)
    app.include_router(product_twin.router, prefix="/api", include_in_schema=False)
    return app


app = create_app()

_LEGACY_TENANT_PREFIXES = (
    "/api/companies", "/api/products", "/api/analysis", "/api/actions",
    "/api/compliance", "/api/developer",
)


@app.middleware("http")
async def guard_legacy_tenant_apis(request, call_next):
    """Keep old routes available for trusted deployments but closed in shared previews."""
    if not get_settings().legacy_tenant_api_enabled and request.url.path.startswith(_LEGACY_TENANT_PREFIXES):
        return JSONResponse({"detail": "Legacy tenant API is disabled"}, status_code=404)
    return await call_next(request)


@app.middleware("http")
async def enforce_local_runtime_token(request, call_next):
    """Local API 需要启动进程生成的短期 token，健康检查例外。"""
    settings = get_settings()
    if settings.runtime_mode == "local" and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        if not settings.runtime_token or request.headers.get("X-Runtime-Token") != settings.runtime_token:
            return JSONResponse({"detail": "Invalid runtime token"}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def prevent_stale_frontend_cache(request, call_next):
    """Avoid serving an old HTML shell that points at assets from a prior deployment."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# 前端开发服务器（Vite 默认 5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in get_settings().application_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由由 create_app 按模式装载。

# The production image serves the compiled React frontend from the same origin.
# During development Vite runs separately and proxies /api to this service.
static_dir = Path(__file__).resolve().parents[1] / "static"
if get_settings().runtime_mode == "web" and static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        candidate = static_dir / path
        if path and candidate.is_file() and static_dir in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
