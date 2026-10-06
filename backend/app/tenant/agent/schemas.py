"""HTTP boundary contracts for synchronous Tenant Intelligence analysis."""

from typing import Literal

from pydantic import Field, model_validator

from app.tenant.applicability.schemas import MissingContextItem
from app.tenant.findings.schemas import TenantAgentRunStatus
from app.understanding.schemas import Contract


class TenantAnalyzeRequest(Contract):
    tenant_id: int = Field(ge=1)
    product_id: int = Field(ge=1)
    trigger_type: Literal["REGULATION_CHANGE", "MANUAL_SCAN"]
    trigger_id: str | None = Field(default=None, max_length=100)
    regulation_id: int | None = Field(default=None, ge=1)
    requirement_ids: list[int] = Field(default_factory=list)
    query: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_trigger(self):
        if self.trigger_type == "REGULATION_CHANGE" and not self.trigger_id:
            raise ValueError("trigger_id is required for REGULATION_CHANGE")
        if self.trigger_type == "MANUAL_SCAN" and self.trigger_id is not None:
            raise ValueError("MANUAL_SCAN does not accept a regulation event trigger_id")
        return self


class TenantAnalyzeResponse(Contract):
    run_id: int
    status: TenantAgentRunStatus
    finding_ids: list[int] = Field(default_factory=list)
    missing_context: list[MissingContextItem] = Field(default_factory=list)
