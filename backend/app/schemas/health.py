"""健康检查响应体。"""

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    """服务健康状态。"""

    status: str = Field(..., description="ok / degraded（数据库不可达时为 degraded）")
    db: str = Field(..., description="postgresql / sqlite")
    llm_provider: str
    embedding_provider: str
