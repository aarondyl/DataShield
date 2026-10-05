"""Stable contracts shared by both analyzers and the User Agent."""
from enum import Enum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Confidence = Annotated[float, Field(ge=0, le=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FindingStatus(str, Enum):
    PRESENT = "PRESENT"
    NOT_DETECTED = "NOT_DETECTED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class AnalysisStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AccessMode(str, Enum):
    FULL = "FULL"
    SELECTED_PATHS = "SELECTED_PATHS"
    METADATA_ONLY = "METADATA_ONLY"
    NO_REPOSITORY = "NO_REPOSITORY"


class Evidence(Contract):
    evidence_id: str
    type: Literal["CODE", "DEPENDENCY", "METADATA", "WEB_PAGE", "PUBLIC_REFERENCE", "USER_DESCRIPTION", "SCAN_SCOPE"]
    file: str | None = None
    url: str | None = None
    symbol: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    reason: str


class Fact(Contract):
    name: str
    status: FindingStatus = FindingStatus.PRESENT
    confidence: Confidence
    evidence_ids: list[str] = Field(default_factory=list)


class TargetUser(Contract):
    type: str
    confidence: Confidence
    evidence_ids: list[str] = Field(default_factory=list)


class MarketClue(Contract):
    jurisdiction: str
    confidence: Confidence
    evidence_ids: list[str] = Field(default_factory=list)


class PublicDocument(Contract):
    present: bool = False
    status: FindingStatus = FindingStatus.UNKNOWN
    url: str | None = None
    confidence: Confidence = 0
    evidence_ids: list[str] = Field(default_factory=list)


class Result(Contract):
    features: list[Fact] = Field(default_factory=list)
    data_types: list[Fact] = Field(default_factory=list)
    vendors: list[Fact] = Field(default_factory=list)
    capabilities: dict[str, Fact] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence = 0
    limitations: list[str] = Field(default_factory=list)
    coverage_complete: bool = False


class RepoAnalysisResult(Result):
    repository_id: str
    analysis_mode: AccessMode
    project_summary: str = "UNKNOWN"
    detected_stack: list[str] = Field(default_factory=list)
    stack_facts: list[Fact] = Field(default_factory=list)
    files_scanned: int = 0


class WebsiteAnalysisResult(Result):
    website_id: str
    url: str
    product_category: str = "UNKNOWN"
    product_category_fact: Fact | None = None
    target_users: list[TargetUser] = Field(default_factory=list)
    market_clues: list[MarketClue] = Field(default_factory=list)
    public_documents: dict[str, PublicDocument] = Field(default_factory=dict)
    pages_analyzed: list[str] = Field(default_factory=list)


class AnalysisConflict(Contract):
    field: str
    repo_value: Fact
    website_value: Fact
    repository_id: str
    website_id: str


class RepositoryRequest(Contract):
    repository_path: str | None = Field(default=None, max_length=4096)
    analysis_mode: AccessMode = AccessMode.METADATA_ONLY
    selected_paths: list[str] = Field(default_factory=list, max_length=100)
    product_description: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_mode(self):
        if self.analysis_mode != AccessMode.NO_REPOSITORY and not self.repository_path:
            raise ValueError("repository_path is required for this analysis mode")
        if self.analysis_mode == AccessMode.SELECTED_PATHS and not self.selected_paths:
            raise ValueError("selected_paths is required for SELECTED_PATHS")
        return self


class WebsiteRequest(Contract):
    url: str = Field(max_length=2048)
    max_depth: int = Field(default=2, ge=0, le=2)
    max_pages: int = Field(default=30, ge=1, le=30)
    product_description: str | None = Field(default=None, max_length=10000)


class AnalysisJob(Contract):
    analysis_id: str
    kind: Literal["repository", "website"]
    status: AnalysisStatus
    created_at: str
    updated_at: str
    repository_analysis: RepoAnalysisResult | None = None
    website_analysis: WebsiteAnalysisResult | None = None
    error: str | None = None


def find_conflicts(repo: RepoAnalysisResult, website: WebsiteAnalysisResult) -> list[AnalysisConflict]:
    """Report differences without choosing a winner or altering either source."""
    conflicts = []
    for group in ("features", "capabilities"):
        left = getattr(repo, group)
        right = getattr(website, group)
        left = list(left.values()) if isinstance(left, dict) else left
        right = list(right.values()) if isinstance(right, dict) else right
        canonical = lambda name: "user_registration" if name == "signup" else name
        indexed = {canonical(f.name): f for f in right}
        for fact in left:
            other = indexed.get(canonical(fact.name))
            if other and fact.status != other.status and FindingStatus.UNKNOWN not in (fact.status, other.status):
                conflicts.append(AnalysisConflict(field=f"{group}.{canonical(fact.name)}", repo_value=fact,
                    website_value=other, repository_id=repo.repository_id, website_id=website.website_id))
    return conflicts
