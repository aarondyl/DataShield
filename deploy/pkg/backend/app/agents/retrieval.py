"""retrieve_regulations 节点：按查询与产品特征检索相关法规条款。

为了提升本地哈希向量的召回质量，检索查询会做特征扩展：
把用户 query 与产品的数据合规特征关键词（健康数据/跨境传输等）拼接后一起向量化。
"""

from __future__ import annotations

from typing import Any

from app.agents.state import AgentState
from app.core.config import get_settings
from app.rag.embeddings import embed_texts_with_fallback
from app.rag.retrieval import get_vector_store

#: 简单识别的欧盟成员国/市场名（用于自动补充 GDPR 相关检索词）
_EU_MARKETS = {
    "germany", "france", "italy", "spain", "netherlands", "belgium", "austria",
    "ireland", "poland", "sweden", "denmark", "finland", "portugal", "greece",
    "czech", "eu", "europe", "欧盟", "欧洲",
}

#: 产品布尔特征 → 检索扩展词
_FEATURE_TERMS: list[tuple[str, str]] = [
    ("collects_health_data", "健康数据 医疗 特殊类别 敏感个人信息"),
    ("collects_sensitive_data", "敏感个人信息 特殊类别 单独同意"),
    ("collects_personal_data", "个人数据 个人信息 告知 同意 合法性基础 处理原则"),
    ("cross_border_data_transfer", "跨境传输 出境 第三国 境外 标准合同 安全评估"),
    ("children_related", "儿童 未成年人 监护人同意"),
    ("third_party_data_sharing", "第三方 共享 委托处理 接收方"),
    ("collects_location_data", "位置数据 行踪轨迹 定位"),
]


def _enrich_query(state: AgentState) -> str:
    """把用户问题与产品特征关键词拼接为检索查询，提升哈希向量召回。"""
    product: dict[str, Any] = state.get("product") or {}
    company: dict[str, Any] = state.get("company") or {}
    parts: list[str] = [state.get("query") or ""]

    for field, terms in _FEATURE_TERMS:
        if product.get(field):
            parts.append(terms)
    if not product.get("has_privacy_policy"):
        parts.append("隐私政策 告知 透明度")

    markets = [str(m).lower() for m in (company.get("target_markets") or product.get("target_markets") or [])]
    if any(m in _EU_MARKETS for m in markets):
        parts.append("GDPR 欧盟 个人数据保护")
    if any(m in ("cn", "china", "中国") for m in markets):
        parts.append("个人信息保护 数据安全")

    description = (product.get("description") or "").strip()
    if description:
        parts.append(description[:100])
    return " ".join(p for p in parts if p)


def retrieve_regulations(state: AgentState) -> dict[str, Any]:
    """检索相关法规条款节点。

    输出 retrieved_chunks：
    [{chunk_id, regulation_name, article_number, content, source_url, jurisdiction, topic}, ...]
    """
    query_text = _enrich_query(state)
    [query_embedding] = embed_texts_with_fallback([query_text])

    filters: dict[str, Any] = {}
    if state.get("regulation_id"):
        filters["regulation_id"] = state["regulation_id"]

    store = get_vector_store()
    top_k = get_settings().retrieval_top_k
    hits = store.search(query_embedding, top_k=top_k, filters=filters)

    chunks = [
        {
            "chunk_id": hit.get("chunk_id"),
            "regulation_id": hit.get("regulation_id"),
            "regulation_name": hit.get("regulation_name", ""),
            "article_number": hit.get("article_number", ""),
            "title": hit.get("title", ""),
            "content": hit.get("content", ""),
            "source_url": hit.get("source_url", ""),
            "jurisdiction": hit.get("jurisdiction", ""),
            "topic": hit.get("topic"),
        }
        for hit in hits
    ]
    return {"retrieved_chunks": chunks}
