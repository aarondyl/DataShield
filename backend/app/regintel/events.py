"""法规变化事件：regulation.change.ready 的构建与持久化。

事件只表达「世界发生了这个法规变化，而且数据库已经可以查询」，
不包含任何「某公司应该如何整改」的推断（那是 User Agent 的工作）。
发布时机：数据库更新 + Requirement Extraction + Chunking + Embedding + 向量索引全部就绪之后。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Regulation, RegulationChange, RegulationEvent, RegulationVersion
from app.models.regulation_change import EVENT_TYPE_CHANGE_READY

#: materiality 严重程度排序（事件取所有变化中的最高级）
_MATERIALITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

#: 主题关键词 → topic 标签（从变化文本中归纳，供下游粗筛）
_TOPIC_KEYWORDS = [
    (("告知", "同意", "consent", "transparen", "透明"), "告知同意/透明度"),
    (("跨境", "境外", "出境", "transfer", "third countr"), "跨境传输"),
    (("敏感", "special categor", "生物识别", "biometric", "健康", "health"), "敏感数据"),
    (("安全", "secur", "加密", "encrypt"), "数据安全"),
    (("儿童", "未成年", "child", "minor"), "未成年人保护"),
    (("评估", "assessment", "审计", "audit"), "影响评估"),
    (("删除", "eras", "delet"), "删除权"),
    (("AI", "人工智能", " automated "), "AI 治理"),
]


def _topics_of(text: str) -> list[str]:
    """从变化文本归纳主题标签（关键词命中即收录）。"""
    lowered = text.lower()
    topics: list[str] = []
    for keywords, topic in _TOPIC_KEYWORDS:
        if any(kw.lower() in lowered for kw in keywords):
            topics.append(topic)
    return topics[:5]


def build_change_ready_payload(
    regulation: Regulation,
    version: RegulationVersion,
    changes: list[RegulationChange],
    requirement_ids: list[int],
    event_id: str,
) -> dict[str, Any]:
    """组装 regulation.change.ready 标准事件报文。"""
    combined_text = "\n".join((c.new_text or "") + (c.old_text or "")[:200] for c in changes)
    materiality = "LOW"
    for change in changes:
        if _MATERIALITY_ORDER.get(change.materiality, 0) > _MATERIALITY_ORDER[materiality]:
            materiality = change.materiality
    return {
        "event_id": event_id,
        "event_type": EVENT_TYPE_CHANGE_READY,
        "schema_version": "1.0",
        "regulation_id": regulation.id,
        "regulation": regulation.name,
        "change_ids": [c.id for c in changes],
        "version_id": version.id,
        "version_number": version.version_number,
        "review_status": version.review_status,
        "jurisdiction": regulation.jurisdiction,
        "topics": _topics_of(combined_text),
        "materiality": materiality,
        "affected_legal_unit_ids": [c.legal_unit_id for c in changes if c.legal_unit_id is not None],
        "requirement_ids": requirement_ids,
    }


def persist_change_ready_event(
    db: Session,
    regulation: Regulation,
    version: RegulationVersion,
    changes: list[RegulationChange],
    requirement_ids: list[int],
) -> RegulationEvent:
    """生成事件 id 并落库（供 User Agent 订阅/查询）。"""
    seq = (db.scalar(select(func.count()).select_from(RegulationEvent)) or 0) + 1
    event_id = f"evt_{seq:06d}"
    payload = build_change_ready_payload(regulation, version, changes, requirement_ids, event_id)
    event = RegulationEvent(
        event_id=event_id,
        event_type=EVENT_TYPE_CHANGE_READY,
        regulation_id=regulation.id,
        version_id=version.id,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event
