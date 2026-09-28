"""分析相关 schema：请求体、LLM 结构化输出校验模型、API 响应体。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisRequest(BaseModel):
    """发起影响分析的请求体。"""

    company_id: int = Field(..., description="企业 ID")
    product_id: int = Field(..., description="产品 ID")
    regulation_id: int | None = Field(None, description="指定分析的法规 ID；为空则全库检索")
    query: str = Field("请分析相关法规对该产品的影响", description="分析诉求/问题")


class EvidenceItem(BaseModel):
    """LLM 输出的证据条目（影响分析节点校验用）。"""

    model_config = ConfigDict(extra="ignore")

    regulation: str = ""
    article: str = ""
    chunk_id: int | str | None = None
    reason: str = ""


class ImpactResult(BaseModel):
    """影响分析结构化结果（LLM JSON 输出的 Pydantic 校验模型）。

    - 证据不足时 relevant 必须为 None、confidence 为 low；
    - 解析/校验失败时由节点生成降级结果，绝不上抛异常。
    """

    model_config = ConfigDict(extra="ignore")

    relevant: bool | None = None
    risk_level: Literal["low", "medium", "high"] = "low"
    affected_products: list[str] = Field(default_factory=list)
    affected_areas: list[str] = Field(default_factory=list)
    summary: str = ""
    reasoning_summary: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"


class EvidenceOut(BaseModel):
    """API 返回的证据条目（含条款内容与真实性校验标记）。"""

    regulation: str = ""
    article: str = ""
    content: str = ""
    source_url: str = ""
    reason: str = ""
    verified: bool = False


class ActionOut(BaseModel):
    """合规整改动作响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    title: str
    priority: str
    department: str
    description: str
    evidence: dict | None = None
    created_at: datetime


class AnalysisOut(BaseModel):
    """分析运行完整结果响应体。"""

    id: int = Field(..., description="分析运行 ID")
    status: str
    relevant: bool | None = None
    risk_level: str | None = None
    affected_products: list[str] = Field(default_factory=list)
    affected_areas: list[str] = Field(default_factory=list)
    summary: str = ""
    reasoning_summary: str = ""
    confidence: str | None = None
    evidence: list[EvidenceOut] = Field(default_factory=list)
    actions: list[ActionOut] = Field(default_factory=list)
    llm_mode: str = ""
    created_at: datetime


class AnalysisListItem(BaseModel):
    """分析运行列表项（含企业/产品名称）。"""

    id: int
    company_name: str
    product_name: str
    risk_level: str | None = None
    relevant: bool | None = None
    status: str
    created_at: datetime
