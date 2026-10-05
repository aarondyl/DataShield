"""法律 chunk 向量检索：Legal Search API 的底层索引。

与 rag/retrieval.py 相同的双后端设计：
- :class:`LocalLegalChunkStore`：SQLite 降级模式的进程内内存余弦检索（只索引 is_active 的 chunk）；
- :class:`PgLegalChunkStore`：PostgreSQL + pgvector 的 cosine distance 检索（生产模式）。

chunk dict 结构：``{chunk_id, regulation_id, regulation_name, version_id, legal_unit_id,
article, content, source_url, jurisdiction, embedding}``。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from sqlalchemy import select

from app.db.session import SessionLocal, is_sqlite
from app.rag.retrieval import _cosine


class LocalLegalChunkStore:
    """本地内存法律 chunk 索引（SQLite 模式使用）。

    索引保存全部 chunk（含已失效），检索时按 ``current_only`` 过滤：
    - ``True``：只检索 is_active 的当前有效 chunk；
    - ``False``：含历史失效 chunk（用于追溯）。
    """

    def __init__(self) -> None:
        self._chunks: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()

    def add(self, chunks: Iterable[dict[str, Any]]) -> None:
        self._chunks.extend(chunks)

    def remove(self, chunk_ids: set[int]) -> None:
        """把已失效的 chunk 标记为 inactive（保留在索引中供历史追溯）。"""
        if not chunk_ids:
            return
        for chunk in self._chunks:
            if chunk.get("chunk_id") in chunk_ids:
                chunk["is_active"] = False

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        jurisdictions: list[str] | None = None,
        regulation_ids: list[int] | None = None,
        current_only: bool = True,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for chunk in self._chunks:
            if current_only and not chunk.get("is_active", True):
                continue
            if jurisdictions and chunk.get("jurisdiction") not in jurisdictions:
                continue
            if regulation_ids and chunk.get("regulation_id") not in regulation_ids:
                continue
            score = _cosine(query_embedding, chunk.get("embedding") or [])
            results.append(dict(chunk, score=score))
        # 相似度降序；同分保持入库顺序（list.sort 稳定，结果确定性）
        results.sort(key=lambda item: -item["score"])
        return results[:top_k]


class PgLegalChunkStore:
    """PostgreSQL + pgvector 法律 chunk 检索（chunk 与向量已在入库阶段写表）。"""

    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

    def add(self, chunks: Iterable[dict[str, Any]]) -> None:
        """pg 模式下 chunk 与向量由入库流程直接写表，此方法无需任何操作。"""
        return None

    def remove(self, chunk_ids: set[int]) -> None:
        return None

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        jurisdictions: list[str] | None = None,
        regulation_ids: list[int] | None = None,
        current_only: bool = True,
    ) -> list[dict[str, Any]]:
        from app.models import LegalChunk, Regulation

        stmt = (
            select(LegalChunk, Regulation)
            .join(Regulation, LegalChunk.regulation_id == Regulation.id)
            .where(LegalChunk.embedding.is_not(None))
        )
        if current_only:
            stmt = stmt.where(LegalChunk.is_active.is_(True))
        if jurisdictions:
            stmt = stmt.where(Regulation.jurisdiction.in_(jurisdictions))
        if regulation_ids:
            stmt = stmt.where(LegalChunk.regulation_id.in_(regulation_ids))

        # pgvector cosine distance：距离越小越相似
        stmt = stmt.order_by(LegalChunk.embedding.cosine_distance(query_embedding)).limit(top_k)

        with self._session_factory() as db:
            rows = db.execute(stmt).all()
        return [
            {
                "chunk_id": chunk.id,
                "regulation_id": regulation.id,
                "regulation_name": regulation.name,
                "version_id": chunk.version_id,
                "legal_unit_id": chunk.legal_unit_id,
                "article": (chunk.metadata_json or {}).get("article", ""),
                "content": chunk.content,
                "source_url": regulation.canonical_source_url or regulation.source_url,
                "jurisdiction": regulation.jurisdiction,
                "embedding": None,
                "score": None,
            }
            for chunk, regulation in rows
        ]


@lru_cache
def get_legal_chunk_store():
    """按数据库后端返回法律 chunk 索引单例。"""
    if is_sqlite():
        return LocalLegalChunkStore()
    return PgLegalChunkStore(SessionLocal)


def index_legal_chunks(chunks: Iterable[dict[str, Any]]) -> None:
    """把新入库的法律 chunk 追加到本地索引（pg 模式为空操作）。"""
    store = get_legal_chunk_store()
    if isinstance(store, LocalLegalChunkStore):
        store.add(list(chunks))


def deactivate_legal_chunks(chunk_ids: set[int]) -> None:
    """把失效 chunk 从本地索引移除（pg 模式检索时按 is_active 过滤，无需操作）。"""
    store = get_legal_chunk_store()
    if isinstance(store, LocalLegalChunkStore):
        store.remove(chunk_ids)


def rebuild_legal_chunk_store_from_db() -> int:
    """从数据库全量重建本地法律 chunk 索引（SQLite 模式启动时调用，含失效 chunk）。"""
    from app.models import LegalChunk, Regulation

    store = get_legal_chunk_store()
    if not isinstance(store, LocalLegalChunkStore):
        return 0
    store.clear()
    stmt = select(LegalChunk, Regulation).join(Regulation, LegalChunk.regulation_id == Regulation.id)
    chunks: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for chunk, regulation in db.execute(stmt).all():
            if not chunk.embedding:
                continue
            chunks.append(
                {
                    "chunk_id": chunk.id,
                    "regulation_id": regulation.id,
                    "regulation_name": regulation.name,
                    "version_id": chunk.version_id,
                    "legal_unit_id": chunk.legal_unit_id,
                    "article": (chunk.metadata_json or {}).get("article", ""),
                    "content": chunk.content,
                    "source_url": regulation.canonical_source_url or regulation.source_url,
                    "jurisdiction": regulation.jurisdiction,
                    "embedding": list(chunk.embedding),
                    "is_active": bool(chunk.is_active),
                }
            )
    store.add(chunks)
    return len(chunks)
