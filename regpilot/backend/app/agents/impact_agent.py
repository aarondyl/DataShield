"""impact_analysis 节点：基于检索条款做法规影响分析。

流程：
1. 把企业/产品画像与检索到的条款组织进 prompt，要求 LLM 输出严格 JSON；
2. 用 Pydantic 模型 :class:`ImpactResult` 校验输出；
3. 证据清洗：chunk_id 必须来自本次 retrieved_chunks，否则丢弃（严禁编造条款）；
4. 任何 LLM 异常 / 解析失败 / 校验失败 → 输出降级结果
   （relevant=null, confidence=low, summary 注明 LLM 不可用），节点绝不崩溃。
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.state import AgentState
from app.core.llm import get_llm_client_safe
from app.schemas.analysis import EvidenceItem, ImpactResult

_SYSTEM_PROMPT = (
    "你是资深数据合规分析师，为出海企业评估法规对产品的影响。"
    "你必须只输出一个 JSON 对象，禁止输出任何其他文字。字段定义："
    '{"relevant": true|false|null（证据不足时为 null）, '
    '"risk_level": "low"|"medium"|"high", '
    '"affected_products": ["产品名"], '
    '"affected_areas": ["受影响业务领域"], '
    '"summary": "影响摘要（中文，2-4 句）", '
    '"reasoning_summary": "推理过程摘要（中文，1-3 句）", '
    '"evidence": [{"regulation": "法规名", "article": "条款号", "chunk_id": 数字, "reason": "引用原因"}], '
    '"confidence": "high"|"medium"|"low"}。'
    "严格要求：evidence 的 chunk_id 必须原样取自给定条款列表，禁止编造条款；"
    "没有可靠证据时 relevant 输出 null、confidence 输出 low、evidence 输出空数组。"
)

_VALID_RISK = {"low", "medium", "high"}
_VALID_CONFIDENCE = {"high", "medium", "low"}


def _build_user_prompt(state: AgentState) -> str:
    """把企业/产品/检索条款组织为用户 prompt（api 模式使用）。"""
    company = state.get("company") or {}
    product = state.get("product") or {}
    chunks = state.get("retrieved_chunks") or []
    chunk_brief = [
        {
            "chunk_id": c.get("chunk_id"),
            "regulation": c.get("regulation_name"),
            "article": c.get("article_number"),
            "jurisdiction": c.get("jurisdiction"),
            "content": (c.get("content") or "")[:600],
        }
        for c in chunks
    ]
    payload = {
        "分析问题": state.get("query") or "",
        "企业": company,
        "产品": product,
        "检索到的条款": chunk_brief,
    }
    return "请基于以下信息输出影响分析 JSON：\n" + json.dumps(payload, ensure_ascii=False)


def _fallback_result(state: AgentState, reason: str) -> ImpactResult:
    """LLM 不可用/输出无效时的降级结果：不崩溃、明确标注、证据为空。"""
    product = state.get("product") or {}
    pname = product.get("name") or "该产品"
    return ImpactResult(
        relevant=None,
        risk_level="low",
        affected_products=[pname],
        affected_areas=[],
        summary=(
            f"LLM 暂不可用（{reason}），本次分析已自动降级：暂无法得出可靠结论，"
            "建议稍后重试或切换 LLM_PROVIDER=mock 体验完整流程。"
        ),
        reasoning_summary=f"影响分析未能执行：{reason}。按规范输出 relevant=null、confidence=low。",
        evidence=[],
        confidence="low",
    )


def _sanitize_llm_json(data: dict[str, Any]) -> dict[str, Any]:
    """对 LLM 原始 JSON 做宽容清洗，降低 Pydantic 校验失败率。"""
    data = dict(data)
    if data.get("risk_level") not in _VALID_RISK:
        data["risk_level"] = "medium"
    if data.get("confidence") not in _VALID_CONFIDENCE:
        data["confidence"] = "low"
    relevant = data.get("relevant")
    if isinstance(relevant, str):
        lowered = relevant.strip().lower()
        data["relevant"] = True if lowered == "true" else (False if lowered == "false" else None)
    if not isinstance(data.get("evidence"), list):
        data["evidence"] = []
    return data


def _clean_evidence(
    evidence: list[EvidenceItem], chunks: list[dict[str, Any]]
) -> list[EvidenceItem]:
    """证据清洗：仅保留能对应到本次检索条款的证据，并把法规名/条款号规范化。

    匹配顺序：chunk_id → (regulation + article) 组合匹配；均不匹配则丢弃。
    """
    by_id = {str(c.get("chunk_id")): c for c in chunks}
    cleaned: list[EvidenceItem] = []
    for item in evidence:
        chunk = by_id.get(str(item.chunk_id)) if item.chunk_id is not None else None
        if chunk is None:
            chunk = next(
                (
                    c
                    for c in chunks
                    if c.get("regulation_name") == item.regulation
                    and c.get("article_number") == item.article
                ),
                None,
            )
        if chunk is None:
            continue  # 编造/无法对应的证据一律丢弃
        cleaned.append(
            EvidenceItem(
                regulation=chunk.get("regulation_name", ""),
                article=chunk.get("article_number", ""),
                chunk_id=chunk.get("chunk_id"),
                reason=item.reason,
            )
        )
    return cleaned


def impact_analysis(state: AgentState) -> dict[str, Any]:
    """影响分析节点。"""
    chunks = state.get("retrieved_chunks") or []
    product = state.get("product") or {}
    client = get_llm_client_safe()

    # 无检索结果：不调用 LLM，直接按"证据不足"输出
    if not chunks:
        result = ImpactResult(
            relevant=None,
            risk_level="low",
            affected_products=[product.get("name") or "该产品"],
            affected_areas=[],
            summary="未检索到相关法规条款，无法评估影响；请先补充法规库后重新分析。",
            reasoning_summary="检索结果为空，证据不足，按规范输出 relevant=null、confidence=low。",
            evidence=[],
            confidence="low",
        )
        return {"impact_result": result.model_dump(mode="json"), "llm_mode": client.provider_name}

    try:
        data = client.chat_json(
            _SYSTEM_PROMPT,
            _build_user_prompt(state),
            context={
                "task": "impact",
                "company": state.get("company") or {},
                "product": product,
                "chunks": chunks,
            },
        )
        result = ImpactResult(**_sanitize_llm_json(data))
    except ValidationError:
        result = _fallback_result(state, "LLM 输出结构不符合约定")
    except Exception as exc:  # LLMError 及一切意外异常统一降级
        result = _fallback_result(state, str(exc))

    # 严禁编造条款：证据必须能对应到本次检索到的 chunk
    result.evidence = _clean_evidence(result.evidence, chunks)

    # 判定相关但没有任何有效证据 → 按"证据不足"降级
    if result.relevant is True and not result.evidence:
        result.relevant = None
        result.confidence = "low"
        result.summary += "（判定相关但缺乏可核验的条款证据，已按证据不足处理。）"
        result.reasoning_summary += " 证据列表为空，结论可信度降级。"

    return {"impact_result": result.model_dump(mode="json"), "llm_mode": client.provider_name}
