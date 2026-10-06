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
from fastapi.staticfiles import StaticFiles

from app.api import actions, analysis, companies, compliance, developer, feedback, findings, health, products, regintel, regulations, remediations, tenant_agent, ui_understanding
from app.api import product_twin, repository_understanding, website_understanding
from app.core.config import get_settings
from app.db.session import SessionLocal, init_db, is_sqlite
from app.rag.retrieval import rebuild_local_store_from_db
from app.regintel.retrieval import rebuild_legal_chunk_store_from_db
from app.services.seed import seed_if_empty
from app.services.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """启动流程：建表 → （SQLite）重建本地向量索引 → 写种子数据（仅当库为空）。"""
    init_db()
    if is_sqlite():
        # 覆盖重启场景：把库里已有的条款向量重新加载进内存索引
        rebuild_local_store_from_db()
        rebuild_legal_chunk_store_from_db()
    if get_settings().run_seed:
        with SessionLocal() as db:
            seed_if_empty(db)
    # 可选：法规来源定时轮询（SCHEDULER_ENABLED=true 时启动）
    scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="DataShield API", version="3.0.0", lifespan=lifespan)


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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (health, companies, products, regulations, regintel, analysis, actions, compliance, developer):
    app.include_router(module.router, prefix="/api")

for module in (tenant_agent, findings, remediations, feedback, ui_understanding):
    app.include_router(module.router, prefix="/api")

app.include_router(website_understanding.router)
app.include_router(website_understanding.router, prefix="/api", include_in_schema=False)
app.include_router(repository_understanding.router)
app.include_router(repository_understanding.router, prefix="/api", include_in_schema=False)
app.include_router(product_twin.router)
app.include_router(product_twin.router, prefix="/api", include_in_schema=False)

# The production image serves the compiled React frontend from the same origin.
# During development Vite runs separately and proxies /api to this service.
static_dir = Path(__file__).resolve().parents[1] / "static"
if static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        candidate = static_dir / path
        if path and candidate.is_file() and static_dir in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
