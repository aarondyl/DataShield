"""产品模型：含数据合规特征布尔字段（影响分析与整改动作生成的核心输入）。"""

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    """企业产品及其数据处理特征画像。"""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="产品名称")
    category: Mapped[str] = mapped_column(String(100), default="", comment="产品品类")
    target_markets: Mapped[list] = mapped_column(JSON, default=list, comment="目标市场列表")

    # ===== 数据合规特征（驱动影响分析与整改动作）=====
    collects_personal_data: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否收集个人数据")
    collects_sensitive_data: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否收集敏感个人信息")
    collects_health_data: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否收集健康数据")
    collects_location_data: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否收集位置数据")
    children_related: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否涉及儿童/未成年人")
    third_party_data_sharing: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否与第三方共享数据")
    uses_third_party_sdk: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否使用第三方 SDK")
    third_party_sdks: Mapped[list] = mapped_column(JSON, default=list, comment="第三方 SDK 名称列表")
    has_privacy_policy: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已有隐私政策")
    privacy_policy_text: Mapped[str] = mapped_column(Text, default="", comment="当前隐私政策文本")
    cross_border_data_transfer: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否存在跨境数据传输")

    description: Mapped[str] = mapped_column(Text, default="", comment="产品描述")

    company: Mapped["Company"] = relationship(back_populates="products")  # noqa: F821
