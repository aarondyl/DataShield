"""LLM 客户端抽象层。

提供两种 provider：
- ``api``：OpenAI 兼容接口（DeepSeek 等），通过 chat completions 的 JSON 模式输出结构化结果；
- ``mock``：离线演示模式，根据输入的产品特征与检索条款输出**确定性**结构化结果，供测试与无 Key 环境使用。

所有 LangGraph 节点通过 :func:`get_llm_client` 获取客户端；
节点侧对 ``LLMError`` 及一切调用异常做捕获并走降级路径，保证服务绝不因 LLM 不可用而崩溃。

本模块同时提供 :func:`rule_based_actions`：不依赖 LLM 的规则式整改动作生成器，
既作为 mock provider 的 action 输出，也作为 api 调用失败时的降级输出。
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


class LLMError(Exception):
    """LLM 调用失败（无 Key、网络错误、返回非 JSON 等）时抛出，由节点捕获降级。"""


class BaseLLMClient(ABC):
    """LLM 客户端接口。"""

    #: provider 标识，写入分析结果的 llm_mode 字段
    provider_name: str = "base"
    model_name: str = ""

    @abstractmethod
    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行一次"输出严格 JSON"的对话调用，返回解析后的 dict。

        :param system_prompt: 系统提示词
        :param user_prompt: 用户提示词
        :param context: 结构化上下文（mock provider 使用；api provider 忽略，
                        因为真实信息已组织进 prompt）
        :raises LLMError: 调用失败或返回无法解析为 JSON 时
        """


# ---------------------------------------------------------------------------
# api provider：OpenAI 兼容接口
# ---------------------------------------------------------------------------


class ApiLLMClient(BaseLLMClient):
    """OpenAI 兼容接口客户端（DeepSeek 等）。"""

    provider_name = "api"

    def __init__(self) -> None:
        settings = get_settings()
        api_key = settings.llm_api_key or ("ollama-local" if settings.desktop_ai_mode == "local" else "")
        if not api_key:
            raise LLMError("未配置 LLM_API_KEY，无法使用 api provider")
        # 延迟导入，避免 mock 模式下也强依赖 openai 包可用
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=settings.llm_base_url)
        self._model = settings.llm_model
        self.provider_name = settings.desktop_ai_mode if settings.runtime_mode == "local" else "api"
        self.model_name = settings.llm_model

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = resp.choices[0].message.content or ""
        except LLMError:
            raise
        except Exception as exc:  # 网络/鉴权/限流等统一包装
            raise LLMError(f"LLM 接口调用失败：{exc}") from exc
        return _parse_json_object(content)


class CloudLLMClient(BaseLLMClient):
    """Authenticated DataShield inference gateway; prompt context is uploaded only after consent."""

    provider_name = "cloud"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.llm_cloud_consent:
            raise LLMError("使用 DataShield Cloud AI 前请先同意将本次分析上下文发送到云端模型服务")
        if not settings.llm_base_url.startswith("https://"):
            raise LLMError("尚未配置 DataShield Cloud Identity 服务地址")
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model_name = settings.llm_model or "deepseek-flash"

    def chat_json(self, system_prompt: str, user_prompt: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        from app.core.cloud_ai import current_cloud_identity_token
        token = current_cloud_identity_token.get()
        if not token:
            raise LLMError("Cloud AI 需要有效的 DataShield 云端登录会话")
        import httpx
        try:
            response = httpx.post(
                f"{self.base_url}/v1/ai/chat-json",
                headers={"Authorization": f"Bearer {token}"},
                json={"system_prompt": system_prompt, "user_prompt": user_prompt},
                timeout=httpx.Timeout(50.0, connect=8.0),
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result")
            if not isinstance(result, dict):
                raise ValueError("invalid structured response")
            self.model_name = str(payload.get("model") or self.model_name)
            return result
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMError("DataShield Cloud AI 请求失败；请检查登录会话和云端服务状态") from exc


def _parse_json_object(content: str) -> dict[str, Any]:
    """从 LLM 文本输出中解析 JSON 对象（容忍 ```json 代码围栏与前后杂文本）。"""
    text = content.strip()
    # 去掉 markdown 代码围栏
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # 截取第一个 { 到最后一个 }，容忍模型在 JSON 前后输出解释文字
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError("LLM 输出中未找到 JSON 对象")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM 输出 JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM 输出不是 JSON 对象")
    return data


# ---------------------------------------------------------------------------
# mock provider：确定性输出（供测试 / 离线 Demo）
# ---------------------------------------------------------------------------

# 关键词表：用于把产品数据特征与条款主题匹配起来（全部小写比较，中文不受大小写影响）
_HEALTH_KW = ["健康", "health", "特殊类别", "special categor", "生物识别", "biometric", "基因", "genetic", "医疗", "敏感个人信息"]
_CROSS_KW = ["跨境", "cross-border", "cross border", "第三国", "third countr", "出境", "境外", "transfer", "传输"]
_PERSONAL_KW = ["个人数据", "personal data", "个人信息", "同意", "consent", "告知", "合法性基础", "lawful", "处理原则"]
_CHILD_KW = ["儿童", "child", "未成年人", "minor"]
_LOCATION_KW = ["位置", "location", "行踪", "轨迹", "定位"]
_SHARE_KW = ["第三方", "third part", "共享", "委托", "接收方", "processor", "受托"]
_SECURITY_KW = ["安全", "secur", "加密", "encrypt", "假名", "pseudonym", "影响评估", "impact assessment", "dpia"]


def _score_chunk(text: str, product: dict[str, Any]) -> tuple[int, list[str]]:
    """按产品布尔特征为单个条款打分，返回 (分数, 命中的主题标签)。"""
    score = 0
    tags: list[str] = []

    def _hit(keywords: list[str]) -> bool:
        return any(k in text for k in keywords)

    if (product.get("collects_health_data") or product.get("collects_sensitive_data")) and _hit(_HEALTH_KW):
        score += 3
        tags.append("特殊类别/敏感数据处理")
    if product.get("cross_border_data_transfer") and _hit(_CROSS_KW):
        score += 2
        tags.append("跨境数据传输")
    if product.get("collects_personal_data") and _hit(_PERSONAL_KW):
        score += 1
        tags.append("个人信息处理")
    if product.get("children_related") and _hit(_CHILD_KW):
        score += 2
        tags.append("未成年人数据保护")
    if product.get("collects_location_data") and _hit(_LOCATION_KW):
        score += 1
        tags.append("位置数据收集")
    if product.get("third_party_data_sharing") and _hit(_SHARE_KW):
        score += 1
        tags.append("第三方数据共享")
    if score > 0 and _hit(_SECURITY_KW):
        score += 1
        tags.append("安全与影响评估")
    return score, tags


def _affected_areas(product: dict[str, Any]) -> list[str]:
    """根据产品布尔特征推导受影响业务领域（确定性顺序）。"""
    areas: list[str] = []
    if product.get("collects_health_data"):
        areas.append("健康数据处理")
    if product.get("collects_sensitive_data"):
        areas.append("敏感个人信息处理")
    if product.get("collects_personal_data"):
        areas.append("个人数据收集与处理")
    if product.get("cross_border_data_transfer"):
        areas.append("跨境数据传输")
    if product.get("third_party_data_sharing"):
        areas.append("第三方数据共享")
    if product.get("children_related"):
        areas.append("未成年人数据保护")
    if product.get("collects_location_data"):
        areas.append("位置数据收集")
    if not product.get("has_privacy_policy"):
        areas.append("隐私政策缺失")
    return areas


def mock_impact(context: dict[str, Any]) -> dict[str, Any]:
    """mock 影响分析：根据产品特征与检索到的条款输出确定性 JSON。

    证据的 chunk_id 严格取自输入的 chunks，绝不编造条款。
    """
    product = context.get("product") or {}
    company = context.get("company") or {}
    chunks: list[dict[str, Any]] = context.get("chunks") or []
    pname = product.get("name") or "该产品"

    base: dict[str, Any] = {
        "relevant": None,
        "risk_level": "low",
        "affected_products": [pname],
        "affected_areas": [],
        "summary": "",
        "reasoning_summary": "",
        "evidence": [],
        "confidence": "low",
    }

    if not chunks:
        base["summary"] = "【模拟分析】法规库中未检索到相关条款，无法评估影响；请先上传/补充法规文本后重新分析。"
        base["reasoning_summary"] = "检索结果为空，证据不足，按规范输出 relevant=null、confidence=low。"
        return base

    scored: list[tuple[int, list[str], dict[str, Any]]] = []
    for chunk in chunks:
        text = f"{chunk.get('article_number', '')} {chunk.get('content', '')}".lower()
        score, tags = _score_chunk(text, product)
        if score > 0:
            scored.append((score, tags, chunk))
    # 分数降序；同分保持检索原顺序（list.sort 稳定，结果确定性）
    scored.sort(key=lambda item: -item[0])

    if not scored:
        base["summary"] = "【模拟分析】检索到的条款与该产品数据特征关联度不足，无法得出可靠结论。"
        base["reasoning_summary"] = "产品特征关键词未命中任何条款内容，证据不足，按规范输出 relevant=null。"
        return base

    top = scored[:3]
    evidence = [
        {
            "regulation": c.get("regulation_name", ""),
            "article": c.get("article_number", ""),
            "chunk_id": c.get("chunk_id"),
            "reason": f"产品涉及「{'、'.join(tags)}」，与 {c.get('regulation_name', '')}{c.get('article_number', '')} 的合规要求直接相关。",
        }
        for score, tags, c in top
    ]

    high_hit = any(score >= 3 for score, _, _ in scored)
    risk = "high" if high_hit else "medium"
    areas = _affected_areas(product)
    regs = "、".join(sorted({c.get("regulation_name", "") for _, _, c in top}))
    markets = "、".join(company.get("target_markets") or []) or "目标市场"

    return {
        "relevant": True,
        "risk_level": risk,
        "affected_products": [pname],
        "affected_areas": areas,
        "summary": (
            f"【模拟分析】{pname} 在{markets}涉及{'、'.join(areas) or '数据处理活动'}，"
            f"与 {regs} 的相关条款存在直接关联，初步判定风险等级为 {risk}。"
        ),
        "reasoning_summary": (
            f"基于检索到的 {len(top)} 条条款证据，按产品数据特征与条款主题的关键词匹配打分得出；"
            f"最高匹配分 {scored[0][0]}，命中主题：{'、'.join(scored[0][1])}。"
        ),
        "evidence": evidence,
        "confidence": "high" if high_hit else "medium",
    }


def rule_based_actions(
    product: dict[str, Any],
    impact: dict[str, Any] | None,
    verified_evidence: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """规则式整改动作生成器（不依赖 LLM）。

    根据产品布尔特征与影响分析结果生成通用整改动作；
    每条动作尽量挂载与主题匹配的已验证证据，无证据时为 None。
    """
    impact = impact or {}
    verified_evidence = verified_evidence or []
    ev0 = verified_evidence[0] if verified_evidence else None

    def evref(keywords: list[str]) -> dict[str, str] | None:
        """在已验证证据中找与关键词主题最相关的一条作为动作依据。"""
        for item in verified_evidence:
            text = f"{item.get('regulation', '')}{item.get('article', '')}{item.get('content', '')}"
            if any(k in text for k in keywords):
                return {"regulation": item.get("regulation", ""), "article": item.get("article", "")}
        if ev0:
            return {"regulation": ev0.get("regulation", ""), "article": ev0.get("article", "")}
        return None

    actions: list[dict[str, Any]] = []

    if product.get("collects_health_data") or product.get("collects_sensitive_data"):
        actions.append(
            {
                "title": "核查特殊类别/健康数据处理的合法性基础并取得明示（单独）同意",
                "priority": "high",
                "department": "Legal",
                "description": (
                    "健康数据、生物识别等属于特殊类别/敏感个人信息，原则上禁止处理。"
                    "需逐项确认处理目的与必要性，取得数据主体的明示（单独）同意，"
                    "并在隐私政策中单独披露处理规则。"
                ),
                "evidence": evref(["第9条", "第29条", "健康", "特殊类别", "敏感", "医疗"]),
            }
        )
    if product.get("collects_personal_data") and not product.get("has_privacy_policy"):
        actions.append(
            {
                "title": "制定并发布隐私政策，落实处理前告知义务",
                "priority": "high",
                "department": "Legal",
                "description": (
                    "产品当前缺少隐私政策。需以显著方式、清晰语言告知处理者身份、处理目的与方式、"
                    "信息种类、保存期限、个人权利行使方式等内容，并留存告知记录。"
                ),
                "evidence": evref(["第17条", "第5条", "告知", "原则", "透明"]),
            }
        )
    if product.get("cross_border_data_transfer"):
        actions.append(
            {
                "title": "建立跨境数据传输合规机制（充分性认定/标准合同/安全评估）",
                "priority": "high",
                "department": "Legal",
                "description": (
                    "向境外传输个人数据须满足法定条件：欧盟侧可采用充分性认定、标准合同条款（SCC）"
                    "等保障措施；中国侧须通过安全评估、认证或订立标准合同，并保障境外接收方保护水平。"
                ),
                "evidence": evref(["第44条", "第38条", "第31条", "跨境", "出境", "第三国", "境外"]),
            }
        )
    if product.get("third_party_data_sharing"):
        actions.append(
            {
                "title": "梳理第三方数据共享清单并签署数据处理协议",
                "priority": "medium",
                "department": "Engineering",
                "description": (
                    "盘点全部第三方 SDK 与合作方的数据共享情况，签署数据处理协议（DPA），"
                    "明确处理目的、安全措施与责任边界，并在隐私政策中公示。"
                ),
                "evidence": evref(["第三方", "共享", "委托", "接收方"]),
            }
        )
    if product.get("children_related"):
        actions.append(
            {
                "title": "建立未成年人个人信息保护专门规则与监护人同意机制",
                "priority": "high",
                "department": "Product",
                "description": (
                    "涉及儿童/未成年人个人信息时，须取得监护人同意并制定专门处理规则，"
                    "上线年龄识别与监护人验证流程。"
                ),
                "evidence": evref(["第31条", "儿童", "未成年人", "监护"]),
            }
        )
    if product.get("collects_location_data"):
        actions.append(
            {
                "title": "评估位置数据收集必要性，落实最小化与单独同意",
                "priority": "medium",
                "department": "Product",
                "description": (
                    "位置/行踪轨迹属于敏感信息，应默认关闭精确采集，仅在核心功能必需时开启，"
                    "并提供清晰的开关与撤回同意入口。"
                ),
                "evidence": evref(["位置", "行踪", "轨迹", "第29条"]),
            }
        )
    if impact.get("risk_level") == "high":
        actions.append(
            {
                "title": "开展数据保护影响评估（DPIA/个人信息保护影响评估）",
                "priority": "high",
                "department": "Security",
                "description": (
                    "初步判定为高风险，须在大规模处理前开展数据保护影响评估，"
                    "识别处理活动对个人权益的风险并采取缓解措施，留存评估报告。"
                ),
                "evidence": evref(["第35条", "第32条", "影响评估", "安全"]),
            }
        )
    if not actions:
        actions.append(
            {
                "title": "建立法规动态监控机制，定期复评产品合规状态",
                "priority": "low",
                "department": "Management",
                "description": (
                    "当前未发现高风险缺口。建议建立法规更新监控与年度合规复评机制，"
                    "确保产品迭代持续符合目标市场要求。"
                ),
                "evidence": None,
            }
        )
    return actions


def mock_actions(context: dict[str, Any]) -> dict[str, Any]:
    """mock 整改动作：直接复用规则式生成器，保证确定性。"""
    return {
        "actions": rule_based_actions(
            context.get("product") or {},
            context.get("impact") or {},
            context.get("verified_evidence") or [],
        )
    }


def mock_remediation_code(context: dict[str, Any]) -> dict[str, Any]:
    """Deterministic grounded code proposal for offline tests and demos."""

    finding = context.get("finding") or {}
    requirements = context.get("requirements") or []
    allowed_paths = context.get("allowed_paths") or []
    target_components = context.get("target_components") or []
    requirement = requirements[0] if requirements else {}
    target = (
        allowed_paths[0]
        if allowed_paths
        else target_components[0]
        if target_components
        else f"{requirement.get('object_type') or 'affected product'} component"
    )
    potential = finding.get("gap_status") == "POTENTIAL"
    change = (
        "Verify the current implementation. If evidence confirms that a change is needed, "
        "add or adjust the control described by the validated requirement."
        if potential
        else "Implement the control described by the validated requirement for the confirmed gap."
    )
    constraints = list(dict.fromkeys([
        *(context.get("user_constraints") or []),
        "Use only the supplied legal requirements and product evidence.",
        "Preserve unrelated behavior.",
    ]))
    return {
        "requested_changes": [{
            "target": target,
            "change": change,
            "rationale": (
                "Address the potential gap while preserving its uncertainty."
                if potential else "Address the confirmed product gap."
            ),
        }],
        "affected_files_or_components": [target],
        "constraints": constraints,
        "acceptance_criteria": [
            "The implemented behavior satisfies the supplied required state and is covered by tests."
        ],
        "tests": [{
            "name": "remediation behavior",
            "purpose": "Verify the requested control using the supplied Finding context.",
            "expected_result": "The required behavior is observable without changing unrelated behavior.",
        }],
        "do_not_modify": ["Unrelated product behavior and legal requirements"],
    }


def mock_remediation_document(context: dict[str, Any]) -> dict[str, Any]:
    """Deterministic grounded document draft using only allowed evidence references."""

    finding = context.get("finding") or {}
    potential = finding.get("gap_status") == "POTENTIAL"
    has_unknown = bool(context.get("has_unknown_facts"))
    qualifier = "potentially required" if potential else "required"
    placeholder = " [TO CONFIRM: verify product-specific details before publication.]" if has_unknown else ""
    return {
        "document_type": context.get("document_type") or "PRODUCT_DOCUMENTATION",
        "proposed_changes": [{
            "section": "Relevant product disclosure",
            "change": f"Add a human-reviewed draft describing the {qualifier} product behavior.",
            "rationale": (
                "Reflect the potential gap without asserting that an unverified control is absent."
                if potential else "Address the confirmed product documentation gap."
            ),
        }],
        "draft_text": (
            "DRAFT — REQUIRES HUMAN REVIEW. Describe the applicable product behavior using only "
            f"verified product facts and the supplied legal requirement.{placeholder}"
        ),
        "draft_status": "DRAFT_REQUIRES_HUMAN_REVIEW",
        "evidence": context.get("allowed_evidence_references") or [],
        "acceptance_criteria": [
            "A human reviewer confirms every product-specific statement before publication."
        ],
    }


class MockLLMClient(BaseLLMClient):
    """离线 mock 客户端：根据 context["task"] 分发到确定性生成函数。"""

    provider_name = "mock"
    model_name = "deterministic"

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        task = context.get("task")
        if task == "impact":
            return mock_impact(context)
        if task == "actions":
            return mock_actions(context)
        if task == "remediation-code":
            return mock_remediation_code(context)
        if task == "remediation-document":
            return mock_remediation_document(context)
        if task == "feedback-candidate":
            facts = context.get("facts") or []
            original = (context.get("raw_feedback") or "").lower()
            answer = (context.get("clarification_answer") or "").lower()
            raw = answer or original
            aliases = {
                "account_deletion": ("account deletion", "删除账号", "删除账户", "注销账号", "注销账户", "账号删除", "账户删除"),
                "ai_disclosure": ("ai disclosure", "disclose ai", "ai告知", "ai提示", "人工智能告知", "人工智能提示"),
                "file_upload": ("file upload", "文件上传", "上传文件"),
                "uploaded": ("upload", "文件上传", "上传文件"),
            }
            def matches(fact, text):
                import re
                name = fact.get("name", "").lower()
                terms = (name, name.replace("_", " "), *aliases.get(name, ()))
                # A short market fact such as US must not match "users".
                return any(term and re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", text) for term in terms)
            targets = [f for f in facts if matches(f, answer)] if answer else []
            if not targets:
                targets = [f for f in facts if matches(f, original)]
            target = targets[0] if len(targets) == 1 else None
            status = None
            if any(w in raw for w in ("not detected", "not_detected", "未检测到", "未发现", "没检测到", "没有检测到", "没有发现")):
                status = "NOT_DETECTED"
            elif any(w in raw for w in ("unknown", "don't know", "do not know", "not sure", "未知", "不知道", "不确定", "不能确定")):
                status = "UNKNOWN"
            elif any(w in raw for w in ("not support", "don't support", "no longer support", "not have", "not available", "does not exist", "absent", "没有", "不支持", "不存在", "未提供", "尚未支持", "尚未实现", "不具备")):
                status = "ABSENT"
            elif any(w in raw for w in ("support", "available", "implemented", "exists", "already", "yes", "支持", "已实现", "存在", "具备", "已经")):
                status = "PRESENT"
            ambiguous = not target or status is None or any(word in raw for word in ("maybe", "planning", "计划", "可能", "准备"))
            chinese = any('\u4e00' <= char <= '\u9fff' for char in original + answer)
            return {"candidate_type":"FACT_CORRECTION","target_fact_id":target.get("fact_id") if target else None,
                "proposed_name":target.get("name") if target else None,"proposed_value":(status == "PRESENT") if not ambiguous and status in ("PRESENT", "ABSENT") else None,
                "proposed_status":status if not ambiguous else None,"confidence":0.85 if not ambiguous else 0.4,
                "reasoning_summary":("确定性模拟解释：保留用户明确描述的事实状态，仍需人工审核。" if chinese else "Deterministic interpretation preserves the explicitly stated fact status; human review is required.") if not ambiguous else ("未能明确定位产品事实或判断当前状态，需要用户澄清。" if chinese else "The feedback does not identify one product fact and its current state."),
                "needs_clarification":ambiguous,"clarification_question":("请明确是哪项产品事实，以及当前是存在、不存在、未知还是未检测到？" if chinese else "Which product fact is meant, and is it present, absent, unknown, or not detected?") if ambiguous else None}
        # 未识别的任务类型：返回空对象，由调用方按"证据不足"降级处理
        return {}


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------


@lru_cache
def get_llm_client() -> BaseLLMClient:
    """按 LLM_PROVIDER 配置返回客户端单例。

    注意：api provider 在缺少 Key 时构造即抛 LLMError，因此本函数不做缓存失败的尝试，
    调用方（节点）需捕获异常并走降级路径。
    """
    settings = get_settings()
    if settings.llm_provider == "cloud":
        return CloudLLMClient()
    if settings.llm_provider == "api":
        if settings.runtime_mode == "local" and settings.desktop_ai_mode == "byok" and not settings.llm_cloud_consent:
            raise LLMError("使用 BYOK 前请先确认本次分析所需上下文会发送给你选择的模型服务商")
        return ApiLLMClient()
    return MockLLMClient()


def get_llm_client_safe() -> BaseLLMClient:
    """仅在显式 Mock 模式降级；真实 Provider 配置错误必须向用户报告。"""
    try:
        return get_llm_client()
    except LLMError:
        if get_settings().desktop_ai_mode == "mock":
            return MockLLMClient()
        raise
