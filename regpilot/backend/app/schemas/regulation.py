"""法规相关 schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArticleOut(BaseModel):
    """法规条款响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    article_number: str
    title: str
    content: str
    topic: str | None = None


class RegulationOut(BaseModel):
    """法规列表项响应体（含条款数）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    jurisdiction: str
    description: str
    source_url: str
    published_at: datetime | None = None
    effective_at: datetime | None = None
    created_at: datetime
    article_count: int = Field(0, description="已入库条款数量")


class RegulationDetailOut(RegulationOut):
    """法规详情响应体（含条款数组）。"""

    articles: list[ArticleOut] = Field(default_factory=list)


class RegulationUploadResult(BaseModel):
    """法规上传结果。"""

    id: int
    name: str
    articles_ingested: int = Field(..., description="成功入库的条款数量")
