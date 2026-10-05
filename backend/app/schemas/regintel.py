"""全局法规智能层 API 的请求/响应 schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LegalSearchRequest(BaseModel):
    """Legal Search 请求体。"""

    query: str = Field(..., description="自然语言检索问题")
    jurisdictions: list[str] = Field(default_factory=list, description="法域过滤，如 [\"EU\", \"CN\"]")
    regulation_ids: list[int] = Field(default_factory=list, description="法规 id 过滤")
    top_k: int = Field(8, ge=1, le=50, description="返回结果数")
    current_only: bool = Field(True, description="是否只检索当前有效 chunk（false 可检索历史版本）")


class LegalSearchResultItem(BaseModel):
    """Legal Search 单条命中。"""

    chunk_id: int
    regulation_id: int
    regulation_name: str
    version_id: int
    legal_unit_id: int | None = None
    article: str = ""
    requirement_ids: list[int] = Field(default_factory=list)
    content: str
    summary: str = ""
    source_url: str = ""
    similarity_score: float | None = None


class LegalSearchResponse(BaseModel):
    """Legal Search 响应体。"""

    results: list[LegalSearchResultItem]


class RequirementOut(BaseModel):
    """结构化义务单元响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    regulation_id: int
    version_id: int
    legal_unit_id: int | None = None
    requirement_type: str
    subject_type: str
    action_type: str
    object_type: str
    conditions: list = Field(default_factory=list, validation_alias="conditions_json")
    exceptions: list = Field(default_factory=list, validation_alias="exceptions_json")
    summary: str
    confidence: float
    status: str
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    created_at: datetime


class LegalUnitOut(BaseModel):
    """法律单元（Evidence API：任何 Finding 可追溯到官方来源）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version_id: int
    regulation_id: int = 0
    regulation_name: str = ""
    unit_type: str
    unit_number: str
    heading: str
    text: str
    path: str
    version_number: int = 0
    is_current_version: bool = False
    official_source_url: str = ""


class VersionOut(BaseModel):
    """法规版本响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    regulation_id: int
    version_number: int
    published_at: datetime | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    source_url: str
    content_hash: str
    retrieved_at: datetime
    is_current: bool


class RegulationInfoOut(BaseModel):
    """法规全局元数据响应体（含当前版本指针）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    title: str = ""
    short_name: str = ""
    official_identifier: str = ""
    jurisdiction: str
    authority: str = ""
    document_type: str = ""
    status: str = ""
    original_language: str = ""
    canonical_source_url: str = ""
    description: str = ""
    published_at: datetime | None = None
    effective_at: datetime | None = None
    current_version_id: int | None = None
    current_version_number: int | None = None
    article_count: int = 0
    requirement_count: int = 0
    created_at: datetime


class ChangeOut(BaseModel):
    """条级变化响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    regulation_id: int
    regulation_name: str = ""
    from_version_id: int | None = None
    to_version_id: int | None = None
    legal_unit_id: int | None = None
    article: str = ""
    change_type: str
    old_text: str
    new_text: str
    semantic_summary: str
    materiality: str
    requirement_ids: list = Field(default_factory=list)
    source_url: str = ""
    detected_at: datetime


class SourceOut(BaseModel):
    """官方来源响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    regulation_id: int | None = None
    jurisdiction: str
    authority: str
    source_name: str
    base_url: str
    fetch_url: str
    source_type: str
    parser_type: str
    priority: int
    polling_interval: int
    is_active: bool
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None


class IngestionRunOut(BaseModel):
    """入库流水线运行记录响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None = None
    regulation_id: int | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    from_version_id: int | None = None
    to_version_id: int | None = None
    changes_count: int
    requirements_count: int
    chunks_count: int
    error: str = ""
    event_id: int | None = None


class EventOut(BaseModel):
    """法规变化事件响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    event_type: str
    schema_version: str
    regulation_id: int | None = None
    version_id: int | None = None
    payload: dict
    created_at: datetime
