"""Requirement Extraction：把法律条文转化为结构化义务单元。

输出「什么主体在什么条件下需要做什么」，**不做**「该主体是否适用于某公司」的判断
（那是 User Agent 的工作）。

两阶段策略（能用确定性程序完成的事情不交给 LLM）：
1. 规则提取：按中/英文义务句式（应当/不得/有权/shall/may…）做确定性抽取，离线可用；
2. LLM 增强：``LLM_PROVIDER=api`` 时对条文调用 LLM 输出结构化 JSON，
   经 Pydantic 校验后采用；任何失败自动回退规则提取。

置信度 < 0.7 的结果标记为 NEEDS_REVIEW，不静默当成确定事实。
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.llm import get_llm_client_safe
from app.models.requirement import CONFIDENCE_REVIEW_THRESHOLD

# ---------------------------------------------------------------------------
# 中英文义务句式与主体/动作/对象词典
# ---------------------------------------------------------------------------

#: (标记词, requirement_type, 基础置信度)
_CN_MARKERS = [
    ("不得", "prohibition", 0.88),
    ("禁止", "prohibition", 0.9),
    ("应当", "obligation", 0.85),
    ("必须", "obligation", 0.88),
    ("有权", "right", 0.8),
    ("可以", "permission", 0.6),
]

#: 义务主体识别（按出现优先级）
_CN_SUBJECTS = [
    "个人信息处理者", "关键信息基础设施运营者", "国家机关", "网络运营者", "数据处理者",
    "重要数据的处理者", "受托人", "第三方", "任何组织、个人", "任何组织或者个人", "个人",
]

#: 动作关键词 → action_type
_CN_ACTIONS = [
    ("告知", "inform"), ("同意", "obtain_consent"), ("删除", "delete"), ("更正", "rectify"),
    ("保存", "retain"), ("留存", "retain"), ("存储", "store"), ("评估", "assess"),
    ("审计", "audit"), ("提供", "provide"), ("公开", "disclose"), ("加密", "encrypt"),
    ("去标识", "deidentify"), ("匿名化", "anonymize"), ("备份", "backup"), ("报告", "report"),
    ("备案", "file_record"), ("认证", "certify"), ("监测", "monitor"), ("停止", "cease"),
    ("转移", "transfer"), ("传输", "transfer"), ("收集", "collect"), ("共享", "share"),
    ("委托", "entrust"), ("响应", "respond"), ("记录", "record"), ("保护", "protect"),
]

#: 作用对象关键词 → object_type
_CN_OBJECTS = [
    "敏感个人信息", "个人信息", "个人生物识别信息", "重要数据", "核心数据",
    "未成年人个人信息", "数据", "个人权益",
]

_EN_MARKERS = [
    ("shall not", "prohibition", 0.88),
    ("may not", "prohibition", 0.85),
    ("shall", "obligation", 0.82),
    ("must", "obligation", 0.85),
    ("have the right", "right", 0.82),
    ("right to", "right", 0.78),
    ("may ", "permission", 0.6),
]

_EN_SUBJECTS = [
    "provider", "deployer", "importer", "distributor",
    "controller", "processor", "data subject", "supervisory authority",
    "member state", "recipient", "third party", "person",
]

_EN_ACTIONS = [
    ("inform", "inform"), ("consent", "obtain_consent"), ("erase", "delete"), ("rectif", "rectify"),
    ("retain", "retain"), ("store", "store"), ("assess", "assess"), ("audit", "audit"),
    ("provide", "provide"), ("disclose", "disclose"), ("encrypt", "encrypt"),
    ("pseudonym", "pseudonymize"), ("notif", "notify"), ("record", "record"),
    ("transfer", "transfer"), ("collect", "collect"), ("monitor", "monitor"),
    ("designate", "designate"), ("document", "document"), ("restrict", "restrict"),
]

_EN_OBJECTS = [
    "general-purpose ai model", "ai system", "artificial intelligence",
    "personal data", "special categories", "biometric data", "genetic data",
    "health data", "data subject", "processing",
]

_CN_SENTENCE_SPLIT = re.compile(r"[。；;\n]+")
_EN_SENTENCE_SPLIT = re.compile(r"(?<=[.;:])\s+|\n+")


def _detect_cn(sentence: str, table: list[tuple[str, str]]) -> str:
    for keyword, label in table:
        if keyword in sentence:
            return label
    return ""


def _first_match(sentence: str, candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in sentence:
            return candidate
    return ""


def _extract_cn_conditions(sentence: str) -> tuple[list[str], list[str]]:
    """抽取「在……情形下」类条件与「除外」类例外（尽力而为，抽不到返回空）。"""
    conditions = re.findall(r"(?:(?<=在)|(?<=当))([^。；，]{2,40}?(?:时|情况下|情形下))", sentence)
    exceptions = re.findall(r"([^。；，]{2,30}?)(?=的除外|除外[，。；]?)", sentence) if "除外" in sentence else []
    return conditions, exceptions


def _status_of(confidence: float) -> str:
    return "ACTIVE" if confidence >= CONFIDENCE_REVIEW_THRESHOLD else "NEEDS_REVIEW"


def extract_requirements_rule(
    unit_number: str,
    text: str,
    *,
    language: str = "zh",
    default_subject: str = "",
) -> list[dict[str, Any]]:
    """规则式义务提取（确定性，离线可用）。

    按句子扫描义务句式标记词，命中即输出一条结构化义务；
    置信度 = 标记词基础置信度 + 主体/对象命中加成，封顶 0.95。
    """
    results: list[dict[str, Any]] = []
    if not text:
        return results

    if language == "zh":
        sentences = [s.strip() for s in _CN_SENTENCE_SPLIT.split(text) if len(s.strip()) >= 8]
        for sentence in sentences:
            for marker, req_type, base_conf in _CN_MARKERS:
                if marker not in sentence:
                    continue
                subject = _first_match(sentence, _CN_SUBJECTS) or default_subject
                action = _detect_cn(sentence, _CN_ACTIONS) or "other"
                obj = _first_match(sentence, _CN_OBJECTS)
                conditions, exceptions = _extract_cn_conditions(sentence)
                confidence = base_conf + (0.05 if subject else 0.0) + (0.05 if obj else 0.0)
                results.append(
                    {
                        "requirement_type": req_type,
                        "subject_type": subject,
                        "action_type": action,
                        "object_type": obj,
                        "conditions": conditions,
                        "exceptions": exceptions,
                        "summary": sentence[:120],
                        "confidence": round(min(confidence, 0.95), 2),
                    }
                )
                break  # 一句只取最强的一个标记词
    else:
        lowered = text.lower()
        sentences = [s.strip() for s in _EN_SENTENCE_SPLIT.split(lowered) if len(s.strip()) >= 15]
        for sentence in sentences:
            for marker, req_type, base_conf in _EN_MARKERS:
                if marker not in sentence:
                    continue
                subject = _first_match(sentence, _EN_SUBJECTS) or default_subject
                action = _detect_cn(sentence, _EN_ACTIONS) or "other"
                obj = _first_match(sentence, _EN_OBJECTS)
                conditions = re.findall(r"(?:where|when|if) ([^.;]{5,80})", sentence)
                confidence = base_conf + (0.05 if subject else 0.0) + (0.05 if obj else 0.0)
                results.append(
                    {
                        "requirement_type": req_type,
                        "subject_type": subject,
                        "action_type": action,
                        "object_type": obj,
                        "conditions": conditions,
                        "exceptions": [],
                        "summary": sentence[:160],
                        "confidence": round(min(confidence, 0.95), 2),
                    }
                )
                break
    # 同一条款内按 (类型, 主体, 动作, 对象) 去重
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in results:
        key = (item["requirement_type"], item["subject_type"], item["action_type"], item["object_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


# ---------------------------------------------------------------------------
# LLM 增强提取（api provider 时启用，失败回退规则提取）
# ---------------------------------------------------------------------------


class LLMRequirementItem(BaseModel):
    """LLM 输出的单条义务（Pydantic 校验）。"""

    requirement_type: str = "obligation"
    subject_type: str = ""
    action_type: str = ""
    object_type: str = ""
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    summary: str = ""
    confidence: float = 0.5


class LLMRequirementsPayload(BaseModel):
    """LLM 输出的义务列表包装。"""

    requirements: list[LLMRequirementItem] = Field(default_factory=list)


_SYSTEM_PROMPT = (
    "你是法规义务抽取器。从给定法条中抽取结构化义务：什么主体在什么条件下需要做什么。"
    "只输出 JSON：{\"requirements\": [{\"requirement_type\": obligation|prohibition|right|permission,"
    " \"subject_type\": 主体, \"action_type\": 动作, \"object_type\": 对象,"
    " \"conditions\": [...], \"exceptions\": [...], \"summary\": 一句话摘要, \"confidence\": 0-1}]}。"
    "不确定的义务给低置信度；不做任何关于具体公司适用性的判断。"
)


def extract_requirements_llm(unit_number: str, text: str) -> list[dict[str, Any]] | None:
    """用 LLM 提取义务并做 Pydantic 校验；非 api provider 或任何失败返回 None。"""
    if get_settings().llm_provider != "api":
        return None
    try:
        client = get_llm_client_safe()
        data = client.chat_json(
            _SYSTEM_PROMPT,
            f"法条 {unit_number}：\n{text[:6000]}",
            context={"task": "requirement_extraction", "unit_number": unit_number},
        )
        payload = LLMRequirementsPayload.model_validate(data)
    except Exception:  # 网络/鉴权/解析/校验等任何失败都回退规则提取
        return None
    return [item.model_dump() for item in payload.requirements]


def extract_requirements(
    unit_number: str,
    text: str,
    *,
    language: str = "zh",
    default_subject: str = "",
    use_llm: bool = False,
) -> list[dict[str, Any]]:
    """义务提取入口：可选 LLM 增强，失败/未启用时走规则提取。结果带 status 字段。"""
    items = extract_requirements_llm(unit_number, text) if use_llm else None
    if items is None:
        items = extract_requirements_rule(
            unit_number, text, language=language, default_subject=default_subject
        )
    for item in items:
        item.setdefault("requirement_type", "obligation")
        item.setdefault("conditions", [])
        item.setdefault("exceptions", [])
        item["status"] = _status_of(float(item.get("confidence") or 0.0))
    return items
