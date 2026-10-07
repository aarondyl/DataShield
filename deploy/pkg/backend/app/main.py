"""FastAPI 应用入口：CORS、路由注册、启动时建表 + 种子数据 + 向量索引重建。

当前路由分组（路由模块均位于 ``app.api``）：

- ``auth``：注册 / 登录 / 会话（邮箱验证码、Bearer token），新版 AppShell 依赖 ``/api/auth/me``；
- ``evaluation``：评估工作区（``evaluation``、``today``、``findings``、``remediations``、``feedback``、
  ``ui_understanding``，以及 website / repository / product_twin 产品理解链路）；
- ``tenant``：旧版租户 API（``companies``、``products``、``analysis``、``actions``、``compliance``、
  ``developer``），共享预览环境可通过 ``LEGACY_TENANT_API_ENABLED=false`` 整体关闭；
- ``regintel``：法规智能层（``regulations``、``regintel``，条文级法规库、版本追踪与检索）；
- ``health``：健康检查。

本地开发启动::

    DATABASE_URL=sqlite:///./datashield.db LLM_PROVIDER=mock EMBEDDING_PROVIDER=local \
        uvicorn app.main:app --reload

Docker/PostgreSQL 部署时先执行 ``alembic upgrade head`` 再启动（见 Dockerfile）。
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import actions, admin, analysis, auth, companies, compliance, developer, evaluation, feedback, findings, health, products, regintel, regulations, remediations, tenant_agent, today, ui_understanding
from app.api import product_twin, repository_understanding, website_understanding
from app.core.config import get_settings
from app.core.evaluation_auth import verify_runtime_token
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
async def prevent_stale_frontend_cache(request, call_next):
    """Avoid serving an old HTML shell that points at assets from a prior deployment."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.middleware("http")
async def enforce_desktop_runtime_token(request, call_next):
    """桌面模式下校验 Electron 主进程注入的运行时 token，防止本机进程盗用内嵌后端。

    仅 desktop_mode 且环境变量 DATASHIELD_RUNTIME_TOKEN 存在时生效；
    /api/health（主进程轮询就绪）与非 /api 路径（前端静态资源）放行。
    """
    path = request.url.path
    if path.startswith("/api") and path != "/api/health":
        try:
            verify_runtime_token(request)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return await call_next(request)

# 前端开发服务器（Vite 默认 5173）；桌面模式下渲染进程 Origin 不固定（dev 为
# http://localhost:5173，生产 file:// 页面常为 null），放开为正则匹配。
_cors_kwargs = (
    {"allow_origin_regex": ".*", "allow_origins": []}
    if get_settings().desktop_mode
    else {"allow_origins": [origin.strip() for origin in get_settings().application_origins.split(",") if origin.strip()]}
)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **_cors_kwargs,
)

for module in (health, companies, products, regulations, regintel, analysis, actions, compliance, developer):
    app.include_router(module.router, prefix="/api")

for module in (evaluation, auth, admin, tenant_agent, findings, remediations, feedback, today, ui_understanding):
    app.include_router(module.router, prefix="/api")

app.include_router(website_understanding.router)
app.include_router(website_understanding.router, prefix="/api", include_in_schema=False)
app.include_router(repository_understanding.router)
app.include_router(repository_understanding.router, prefix="/api", include_in_schema=False)
app.include_router(product_twin.router)
app.include_router(product_twin.router, prefix="/api", include_in_schema=False)

# The production image serves the compiled React frontend from the same origin.
# During development Vite runs separately and proxies /api to this service.
# Desktop (Electron) packaging points DATASHIELD_FRONTEND_DIR at the bundled frontend.
import os as _os

_frontend_env = _os.environ.get("DATASHIELD_FRONTEND_DIR")
static_dir = Path(_frontend_env).resolve() if _frontend_env else Path(__file__).resolve().parents[1] / "static"
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
