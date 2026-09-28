"""evidence_verification 节点：校验影响分析中证据的真实性。

校验规则：
- 逐条核对 evidence 的 regulation/article 是否真实存在于本次 retrieved_chunks
  （先按 chunk_id 精确匹配，再按 regulation+article 组合匹配兜底）；
- 输出 {verified, unsupported_claims, verified_evidence, should_retry}：
  - verified_evidence / unsupported_claims 均补齐 content、source_url、verified 标记，
    供 action 节点与最终落库使用；
  - 判定"相关"（relevant=true）但主要结论无证据支持，或存在编造证据时 verified=false；
  - verified=false 且 retry_count<1 时 should_retry=true 并把 retry_count+1，
    由条件边回退到 impact_analysis 重跑（最多重试 1 次）。
"""

from __future__ import annotations

from typing import Any

from app.agents.state import AgentState

#: 证据不足允许重跑 impact_analysis 的最大次数
MAX_RETRY = 1


def _enrich(chunk: dict[str, Any], reason: str, verified: bool) -> dict[str, Any]:
    """把证据条目与检索条款合并为完整证据（含内容与来源）。"""
    return {
        "regulation": chunk.get("regulation_name", ""),
        "article": chunk.get("article_number", ""),
        "chunk_id": chunk.get("chunk_id"),
        "content": chunk.get("content", ""),
        "source_url": chunk.get("source_url", ""),
        "reason": reason,
        "verified": verified,
    }


def evidence_verification(state: AgentState) -> dict[str, Any]:
    """证据真实性校验节点。"""
    chunks: list[dict[str, Any]] = state.get("retrieved_chunks") or []
    impact: dict[str, Any] = state.get("impact_result") or {}
    by_id = {str(c.get("chunk_id")): c for c in chunks}

    verified_evidence: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []

    for ev in impact.get("evidence") or []:
        chunk = by_id.get(str(ev.get("chunk_id"))) if ev.get("chunk_id") is not None else None
        if chunk is None:
            chunk = next(
                (
                    c
                    for c in chunks
                    if c.get("regulation_name") == ev.get("regulation")
                    and c.get("article_number") == ev.get("article")
                ),
                None,
            )
        if chunk is None:
            unsupported.append(
                {
                    "regulation": ev.get("regulation", ""),
                    "article": ev.get("article", ""),
                    "chunk_id": ev.get("chunk_id"),
                    "content": "",
                    "source_url": "",
                    "reason": ev.get("reason", ""),
                    "verified": False,
                }
            )
        else:
            verified_evidence.append(_enrich(chunk, ev.get("reason", ""), True))

    relevant = impact.get("relevant")
    has_support = len(verified_evidence) > 0
    # 存在编造证据则不通过；判定相关但无证据支持同样不通过
    verified = not unsupported and (relevant is not True or has_support)

    retry_count = state.get("retry_count", 0)
    should_retry = (not verified) and retry_count < MAX_RETRY

    return {
        "evidence_result": {
            "verified": verified,
            "unsupported_claims": unsupported,
            "verified_evidence": verified_evidence,
            "should_retry": should_retry,
        },
        "retry_count": retry_count + (1 if should_retry else 0),
    }
