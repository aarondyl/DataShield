"""action_planning 节点：根据影响分析与已验证证据生成合规整改动作。

LLM 路径：要求输出 {"actions": [...]} 并用 :class:`ActionItem` 逐条校验；
降级路径（LLM 异常 / 输出为空 / 校验失败）：使用规则式生成器
:func:`app.core.llm.rule_based_actions`（依据产品布尔特征输出通用整改动作）。
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agents.state import AgentState
from app.core.llm import get_llm_client_safe, rule_based_actions
from app.schemas.action import ActionItem

_SYSTEM_PROMPT = (
    "你是资深合规顾问。基于影响分析结论与已验证的法规证据，为企业生成可落地的合规整改动作。"
    "你必须只输出一个 JSON 对象，禁止输出任何其他文字，结构为："
    '{"actions": [{"title": "动作标题", "priority": "low"|"medium"|"high", '
    '"department": "Legal"|"Product"|"Engineering"|"Security"|"Operations"|"Supply Chain"|"Management", '
    '"description": "具体执行说明（中文）", "evidence": {"regulation": "法规名", "article": "条款号"} 或 null}]}。'
    "要求：动作必须针对产品真实的数据处理特征，每条动作尽量引用已验证证据；动作数量 1-8 条。"
)


def _build_user_prompt(state: AgentState) -> str:
    payload = {
        "产品": state.get("product") or {},
        "企业": state.get("company") or {},
        "影响分析": state.get("impact_result") or {},
        "已验证证据": (state.get("evidence_result") or {}).get("verified_evidence") or [],
    }
    return "请基于以下信息输出整改动作 JSON：\n" + json.dumps(payload, ensure_ascii=False)


def action_planning(state: AgentState) -> dict[str, Any]:
    """整改动作生成节点。"""
    product = state.get("product") or {}
    impact = state.get("impact_result") or {}
    evidence_result = state.get("evidence_result") or {}
    verified_evidence: list[dict[str, Any]] = evidence_result.get("verified_evidence") or []

    client = get_llm_client_safe()
    actions: list[dict[str, Any]] = []
    try:
        data = client.chat_json(
            _SYSTEM_PROMPT,
            _build_user_prompt(state),
            context={
                "task": "actions",
                "product": product,
                "impact": impact,
                "verified_evidence": verified_evidence,
            },
        )
        raw = data.get("actions") if isinstance(data, dict) else None
        if not isinstance(raw, list) or not raw:
            raise ValueError("LLM 未返回有效 actions 数组")
        actions = [ActionItem(**item).model_dump(mode="json") for item in raw[:8] if isinstance(item, dict)]
        if not actions:
            raise ValueError("LLM 返回的 actions 全部未通过校验")
    except (ValidationError, ValueError):
        actions = rule_based_actions(product, impact, verified_evidence)
    except Exception:
        # LLMError 及一切意外异常统一走规则降级
        actions = rule_based_actions(product, impact, verified_evidence)

    return {"actions": actions}
