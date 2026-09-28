"""Deterministic DataShield compliance self-assessment records."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    hits: Mapped[list] = mapped_column(JSON, nullable=False)
    dimension_scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    report_markdown: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
