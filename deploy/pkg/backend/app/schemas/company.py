"""企业相关 schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyCreate(BaseModel):
    """创建企业请求体。"""

    name: str = Field(..., min_length=1, max_length=200, description="企业名称")
    industry: str = Field("", max_length=100, description="所属行业")
    country: str = Field("", max_length=100, description="所在国家/地区")
    target_markets: list[str] = Field(default_factory=list, description="目标市场列表")
    business_model: str = Field("", max_length=500, description="商业模式描述")


class CompanyUpdate(BaseModel):
    """更新企业请求体（全部字段可选，仅更新传入字段）。"""

    name: str | None = Field(None, min_length=1, max_length=200)
    industry: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    target_markets: list[str] | None = None
    business_model: str | None = Field(None, max_length=500)


class CompanyOut(BaseModel):
    """企业响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    industry: str
    country: str
    target_markets: list[str]
    business_model: str
    created_at: datetime
