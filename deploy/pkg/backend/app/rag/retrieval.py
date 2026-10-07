"""向量存储抽象与检索。

两种实现，按数据库后端自动切换：
- :class:`LocalVectorStore`：进程内内存余弦相似度检索（SQLite 降级模式）；
- :class:`PgVectorStore`：PostgreSQL + pgvector 的 cosine distance 检索（生产模式）。

检索统一先做 metadata filter（jurisdiction / regulation_name / topic / regulation_id），
再按相似度排序取 top-k。

chunk 统一为 dict 结构：
``{chunk_id, regulation_id, regulation_name, article_number, title, content,
source_url, jurisdiction, topic, embedding}``
其中 ``chunk_id`` 即 regulation_articles 表主键，供证据引用与真实性校验使用。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Iterable

from sqlalchemy import select

from app.db.session import SessionLocal, is_sqlite

#: 检索时支持的 metadata 过滤字段（chunk dict 的键）
FILTER_KEYS = ("regulation_id", "regulation_name", "jurisdiction", "topic")


class VectorStore(ABC):
    """向量存储接口。"""

    @abstractmethod
    def add(self, chunks: list[dict[str, Any]]) -> None:
        """把带 embedding 的条款 chunk 加入索引。"""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """先按 filters 过滤，再按与 query_embedding 的余弦相似度排序，返回 top-k 个 chunk（附 score）。"""


def _match_filters(chunk: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    """判断 chunk 是否满足 metadata 过滤条件（全部条件取等值匹配）。"""
    if not filters:
        return True
    for key, value in filters.items():
        if value is None or key not in FILTER_KEYS:
            continue
        if chunk.get(key) != value:
            return False
    return True


def _cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度；两侧均已归一化时退化为点积，此处仍做防御性归一化。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class LocalVectorStore(VectorStore):
    """本地内存向量索引（SQLite 模式使用）。

    纯内存结构：启动时从数据库重建，法规入库时增量追加。
    """

    def __init__(self) -> None:
        self._chunks: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        """清空索引（重建前调用）。"""
        self._chunks.clear()

    def add(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks.extend(chunks)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        scored = [
            (_cosine(query_embedding, chunk.get("embedding") or []), chunk)
            for chunk in self._chunks
            if _match_filters(chunk, filters)
        ]
        # 相似度降序；同分保持入库顺序（list.sort 稳定，结果确定性）
        scored.sort(key=lambda item: -item[0])
        return [dict(chunk, score=score) for score, chunk in scored[:top_k]]


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector 向量检索（条款与向量已在入库阶段写入 regulation_articles 表）。"""

    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

    def add(self, chunks: list[dict[str, Any]]) -> None:
        """pg 模式下条款与向量由入库流程直接写表，此方法无需任何操作。"""
        return None

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        # 延迟导入，避免模块加载顺序问题
        from app.models import Regulation, RegulationArticle

        filters = filters or {}
        stmt = (
            select(RegulationArticle, Regulation)
            .join(Regulation, RegulationArticle.regulation_id == Regulation.id)
            .where(RegulationArticle.embedding.is_not(None))
        )
        # metadata filter（与 LocalVectorStore 语义一致）
        if filters.get("regulation_id") is not None:
            stmt = stmt.where(RegulationArticle.regulation_id == filters["regulation_id"])
        if filters.get("regulation_name"):
            stmt = stmt.where(Regulation.name == filters["regulation_name"])
        if filters.get("jurisdiction"):
            stmt = stmt.where(Regulation.jurisdiction == filters["jurisdiction"])
        if filters.get("topic"):
            stmt = stmt.where(RegulationArticle.topic == filters["topic"])

        # pgvector cosine distance：距离越小越相似
        distance = RegulationArticle.embedding.cosine_distance(query_embedding)
        stmt = stmt.order_by(distance).limit(top_k)

        with self._session_factory() as db:
            rows = db.execute(stmt).all()
        results: list[dict[str, Any]] = []
        for article, regulation in rows:
            results.append(
                {
                    "chunk_id": article.id,
                    "regulation_id": regulation.id,
                    "regulation_name": regulation.name,
                    "article_number": article.article_number,
                    "title": article.title,
                    "content": article.content,
                    "source_url": regulation.source_url,
                    "jurisdiction": regulation.jurisdiction,
                    "topic": article.topic,
                    "embedding": None,  # 检索结果不回传向量
                    "score": None,
                }
            )
        return results


@lru_cache
def get_vector_store() -> VectorStore:
    """按数据库后端返回向量存储单例。"""
    if is_sqlite():
        return LocalVectorStore()
    return PgVectorStore(SessionLocal)


def index_chunks(chunks: Iterable[dict[str, Any]]) -> None:
    """把新入库的条款 chunk 追加到向量索引（仅本地内存索引需要；pg 模式直接查表）。"""
    store = get_vector_store()
    if isinstance(store, LocalVectorStore):
        store.add(list(chunks))


def rebuild_local_store_from_db() -> int:
    """从数据库全量重建本地内存索引（SQLite 模式启动时调用），返回索引条款数。"""
    from app.models import Regulation, RegulationArticle

    store = get_vector_store()
    if not isinstance(store, LocalVectorStore):
        return 0
    store.clear()
    stmt = select(RegulationArticle, Regulation).join(
        Regulation, RegulationArticle.regulation_id == Regulation.id
    )
    chunks: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for article, regulation in db.execute(stmt).all():
            if not article.embedding:
                continue
            chunks.append(
                {
                    "chunk_id": article.id,
                    "regulation_id": regulation.id,
                    "regulation_name": regulation.name,
                    "article_number": article.article_number,
                    "title": article.title,
                    "content": article.content,
                    "source_url": regulation.source_url,
                    "jurisdiction": regulation.jurisdiction,
                    "topic": article.topic,
                    "embedding": list(article.embedding),
                }
            )
    store.add(chunks)
    return len(chunks)
