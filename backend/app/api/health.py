"""健康检查接口。"""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import db_kind, engine
from app.schemas.health import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    """服务健康状态：数据库种类/连通性、LLM 与 Embedding provider 配置。"""
    settings = get_settings()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status = "ok"
    except Exception:
        # 数据库不可达时降级展示，接口本身不 500
        status = "degraded"
    return HealthOut(
        status=status,
        db=db_kind(),
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
    )
