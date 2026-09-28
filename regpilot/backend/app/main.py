"""FastAPI 应用入口：CORS、路由注册、启动时建表 + 种子数据 + 向量索引重建。

本地开发启动::

    DATABASE_URL=sqlite:///./regpilot.db LLM_PROVIDER=mock EMBEDDING_PROVIDER=local \
        uvicorn app.main:app --reload

Docker/PostgreSQL 部署时先执行 ``alembic upgrade head`` 再启动（见 Dockerfile）。
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import actions, analysis, companies, health, products, regulations
from app.core.config import get_settings
from app.db.session import SessionLocal, init_db, is_sqlite
from app.rag.retrieval import rebuild_local_store_from_db
from app.services.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """启动流程：建表 → （SQLite）重建本地向量索引 → 写种子数据（仅当库为空）。"""
    init_db()
    if is_sqlite():
        # 覆盖重启场景：把库里已有的条款向量重新加载进内存索引
        rebuild_local_store_from_db()
    if get_settings().run_seed:
        with SessionLocal() as db:
            seed_if_empty(db)
    yield


app = FastAPI(title="RegPilot API", version="0.1.0", lifespan=lifespan)

# 前端开发服务器（Vite 默认 5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (health, companies, products, regulations, analysis, actions):
    app.include_router(module.router, prefix="/api")
