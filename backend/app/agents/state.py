"""LangGraph 工作流的共享状态定义。

节点之间通过该 TypedDict 传递数据；total=False 表示所有键均可缺省，
初始状态只需提供 run_id / company_id / product_id / query 等输入字段。
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """法规影响分析工作流状态。

    各字段含义：
    - run_id / company_id / product_id / regulation_id / query：外部输入；
    - company / product：load_context 节点从数据库加载的企业与产品画像；
    - retrieved_chunks：retrieve_regulations 节点检索到的条款
      {regulation_name, article_number, content, source_url, jurisdiction, chunk_id, ...}；
    - impact_result：impact_analysis 节点输出的结构化影响分析（dict，见 schemas.ImpactResult）；
    - evidence_result：evidence_verification 节点输出
      {verified, unsupported_claims, verified_evidence, should_retry}；
    - actions：action_planning 节点输出的整改动作列表；
    - retry_count：证据校验不通过时的重跑次数（最多重试 1 次）；
    - llm_mode：实际生效的 LLM provider（api / mock）。
    """

    # ---- 输入 ----
    run_id: int
    company_id: int
    product_id: int
    regulation_id: int | None
    query: str

    # ---- 上下文 ----
    company: dict[str, Any]
    product: dict[str, Any]

    # ---- 检索 ----
    retrieved_chunks: list[dict[str, Any]]

    # ---- 分析结果 ----
    impact_result: dict[str, Any] | None
    evidence_result: dict[str, Any] | None
    actions: list[dict[str, Any]]

    # ---- 控制 ----
    retry_count: int
    llm_mode: str
