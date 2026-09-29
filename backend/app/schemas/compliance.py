"""Schemas for DataShield self-assessment and privacy tools."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AssessmentRequest(BaseModel):
    product_id: int
    answers: dict[str, Any]


class AssessmentOut(BaseModel):
    id: int
    product_id: int
    answers: dict[str, Any]
    hits: list[dict[str, Any]]
    dimension_scores: dict[str, int]
    score: int
    rating: str
    counts: dict[str, int]
    roadmap: dict[str, list[dict[str, Any]]]
    related_cases: list[dict[str, Any]]
    report_markdown: str
    created_at: datetime


class PolicyGenerateRequest(BaseModel):
    answers: dict[str, Any]
    product_name: str = "【产品名称】"
    company_name: str = "【公司名称】"
    contact: str = "【联系邮箱】"


class PolicyCheckRequest(BaseModel):
    text: str = Field(min_length=1)
    product_id: int | None = None


class DocumentAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)
