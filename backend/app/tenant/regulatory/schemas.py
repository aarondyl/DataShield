"""Stable regulatory DTOs used by Tenant Intelligence."""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.understanding.schemas import Confidence, Contract


class RegulationSourceContext(Contract):
    regulation_name: str = ""
    jurisdiction: str = ""
    version: int | None = None
    source_url: str = ""
    effective_date: datetime | None = None


class RegulationTrigger(Contract):
    event_id: str
    event_type: str
    regulation_id: int
    version_id: int
    change_id: int | None = None
    change_ids: list[int] = Field(default_factory=list)
    materiality: str = "LOW"
    topics: list[str] = Field(default_factory=list)
    requirement_ids: list[int] = Field(default_factory=list)
    legal_unit_ids: list[int] = Field(default_factory=list)
    change_summaries: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    source: RegulationSourceContext


class RequirementContext(Contract):
    id: int
    regulation_id: int
    version_id: int
    legal_unit_id: int | None = None
    requirement_type: str
    subject_type: str
    action_type: str
    object_type: str
    conditions: list[Any] = Field(default_factory=list)
    exceptions: list[Any] = Field(default_factory=list)
    summary: str
    confidence: Confidence
    status: str
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    regulation_name: str = ""
    jurisdiction: str = ""
    regulation_version: int | None = None
    source_url: str = ""


class LegalEvidence(Contract):
    legal_unit_id: int
    regulation_id: int
    regulation_name: str
    version_id: int
    version: int
    article: str
    heading: str
    content: str
    source_url: str
    effective_date: datetime | None = None
    requirement_ids: list[int] = Field(default_factory=list)
