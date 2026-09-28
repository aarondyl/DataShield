"""企业（公司）模型。"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Company(Base):
    """出海企业档案。"""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="企业名称")
    industry: Mapped[str] = mapped_column(String(100), default="", comment="所属行业")
    country: Mapped[str] = mapped_column(String(100), default="", comment="所在国家/地区")
    target_markets: Mapped[list] = mapped_column(
        JSON, default=list, comment="目标市场列表，如 [\"Germany\", \"France\"]"
    )
    business_model: Mapped[str] = mapped_column(String(500), default="", comment="商业模式描述")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    products: Mapped[list["Product"]] = relationship(  # noqa: F821  前向引用
        back_populates="company", cascade="all, delete-orphan"
    )
