"""产品相关 schema。"""

from pydantic import BaseModel, ConfigDict, Field


class _ProductBase(BaseModel):
    """产品数据合规特征公共字段。"""

    name: str = Field(..., min_length=1, max_length=200, description="产品名称")
    category: str = Field("", max_length=100, description="产品品类")
    target_markets: list[str] = Field(default_factory=list, description="目标市场列表")
    collects_personal_data: bool = Field(False, description="是否收集个人数据")
    collects_sensitive_data: bool = Field(False, description="是否收集敏感个人信息")
    collects_health_data: bool = Field(False, description="是否收集健康数据")
    collects_location_data: bool = Field(False, description="是否收集位置数据")
    children_related: bool = Field(False, description="是否涉及儿童/未成年人")
    third_party_data_sharing: bool = Field(False, description="是否与第三方共享数据")
    has_privacy_policy: bool = Field(False, description="是否已有隐私政策")
    cross_border_data_transfer: bool = Field(False, description="是否存在跨境数据传输")
    description: str = Field("", description="产品描述")


class ProductCreate(_ProductBase):
    """创建产品请求体。"""

    company_id: int = Field(..., description="所属企业 ID")


class ProductUpdate(BaseModel):
    """更新产品请求体（全部字段可选，仅更新传入字段）。"""

    name: str | None = Field(None, min_length=1, max_length=200)
    category: str | None = Field(None, max_length=100)
    target_markets: list[str] | None = None
    collects_personal_data: bool | None = None
    collects_sensitive_data: bool | None = None
    collects_health_data: bool | None = None
    collects_location_data: bool | None = None
    children_related: bool | None = None
    third_party_data_sharing: bool | None = None
    has_privacy_policy: bool | None = None
    cross_border_data_transfer: bool | None = None
    description: str | None = None


class ProductOut(_ProductBase):
    """产品响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
