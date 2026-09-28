"""法规入库流程：文件解析 → 条款切分 → 向量化 → 写库 → 建索引。"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Regulation, RegulationArticle
from app.rag.chunking import split_into_articles
from app.rag.embeddings import embed_texts_with_fallback
from app.rag.retrieval import index_chunks

#: 支持的上传文件类型
SUPPORTED_EXTENSIONS = ("txt", "md", "pdf")


def parse_upload_to_text(filename: str, data: bytes) -> str:
    """把上传文件解析为纯文本。

    - .txt / .md：按 UTF-8 解码（容错忽略坏字符）；
    - .pdf：用 pypdf 逐页提取文本。

    :raises ValueError: 不支持的文件类型或解析失败
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("txt", "md"):
        return data.decode("utf-8", errors="ignore")
    if ext == "pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            raise ValueError(f"PDF 解析失败：{exc}") from exc
    raise ValueError("仅支持 .txt / .md / .pdf 格式的法规文件")


def ingest_regulation_text(
    db: Session,
    *,
    name: str,
    jurisdiction: str = "",
    description: str = "",
    source_url: str = "",
    text: str,
    published_at: datetime | None = None,
    effective_at: datetime | None = None,
    article_topics: dict[str, str] | None = None,
) -> tuple[Regulation, int]:
    """把法规全文解析入库：切条款 → 算向量 → 写 regulation / regulation_articles → 建索引。

    :param article_topics: 可选的 {条款号: 主题标签} 映射（种子数据使用）
    :return: (法规对象, 入库条款数)
    :raises ValueError: 文本中识别不到任何条款结构
    """
    articles = split_into_articles(text)
    if not articles:
        raise ValueError("未能从文本中识别出任何条款（请确认文本包含「第X条」或「Article N」结构）")

    # 条款标题也参与向量化，提升检索召回
    embed_inputs = [f"{a['article_number']} {a['title']}\n{a['content']}" for a in articles]
    embeddings = embed_texts_with_fallback(embed_inputs)

    regulation = Regulation(
        name=name,
        jurisdiction=jurisdiction,
        description=description,
        source_url=source_url,
        published_at=published_at,
        effective_at=effective_at,
    )
    db.add(regulation)
    db.flush()  # 先拿到 regulation.id

    topics = article_topics or {}
    rows: list[RegulationArticle] = []
    for article, embedding in zip(articles, embeddings):
        row = RegulationArticle(
            regulation_id=regulation.id,
            article_number=article["article_number"],
            title=article["title"],
            content=article["content"],
            topic=topics.get(article["article_number"]),
            embedding=embedding,
        )
        db.add(row)
        rows.append(row)
    db.flush()  # 拿到每行条款的主键（作为 chunk_id）

    # 构造索引 chunk 并追加到本地向量索引（pg 模式下 index_chunks 为空操作，检索直接查表）
    chunks: list[dict[str, Any]] = [
        {
            "chunk_id": row.id,
            "regulation_id": regulation.id,
            "regulation_name": regulation.name,
            "article_number": row.article_number,
            "title": row.title,
            "content": row.content,
            "source_url": regulation.source_url,
            "jurisdiction": regulation.jurisdiction,
            "topic": row.topic,
            "embedding": list(row.embedding) if row.embedding else None,
        }
        for row in rows
    ]
    index_chunks(chunks)

    db.commit()
    db.refresh(regulation)
    return regulation, len(rows)
