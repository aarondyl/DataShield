"""法律结构 Chunking：按 article 切 chunk，过长时按 paragraph 细分。

原则：不把整部法规做成一个 embedding，也不无脑每 500 token 砍一刀；
优先按法律结构（Article / Paragraph）切分，保持语义完整。
"""

from __future__ import annotations

from typing import Any

#: 单个 chunk 的最大字符数（超过则按款细分）
MAX_CHUNK_CHARS = 800


def chunk_article(
    unit_number: str,
    heading: str,
    text: str,
    paragraphs: list[str],
    path: str,
) -> list[str]:
    """把一个 article 单元切成 1..N 个 chunk 文本。

    - 全文（标题+正文）不超过 MAX_CHUNK_CHARS → 单 chunk；
    - 超过 → 按款（paragraph）贪心装包，每包都带上条款号与标题作为上下文。
    """
    header = f"{unit_number} {heading}".strip()
    full = f"{header}\n{text}".strip()
    if len(full) <= MAX_CHUNK_CHARS:
        return [full]
    if not paragraphs:
        # 无款可拆：略长则保留完整语义，超长才硬切
        if len(full) <= MAX_CHUNK_CHARS * 2:
            return [full]
        return [full[i : i + MAX_CHUNK_CHARS] for i in range(0, len(full), MAX_CHUNK_CHARS)]

    chunks: list[str] = []
    current = header
    for para in paragraphs:
        if len(current) + len(para) + 1 > MAX_CHUNK_CHARS and current != header:
            chunks.append(current.strip())
            current = f"{header}\n{para}"
        else:
            current = f"{current}\n{para}"
    if current.strip() and current.strip() != header:
        chunks.append(current.strip())
    return chunks or [full]


def build_chunk_payloads(
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """把 article 单元列表展开为待写库的 chunk payload 列表。

    :param articles: [{legal_unit_id?, unit_number, heading, text, paragraphs, path, metadata}]
    :return: [{legal_unit_id, content, token_count, metadata}]
    """
    payloads: list[dict[str, Any]] = []
    for article in articles:
        contents = chunk_article(
            article["unit_number"],
            article.get("heading", ""),
            article.get("text", ""),
            article.get("paragraphs", []),
            article.get("path", ""),
        )
        for content in contents:
            metadata = dict(article.get("metadata") or {})
            metadata["article"] = article["unit_number"]
            metadata["path"] = article.get("path", "")
            payloads.append(
                {
                    "legal_unit_id": article.get("legal_unit_id"),
                    "content": content,
                    "token_count": len(content),
                    "metadata": metadata,
                }
            )
    return payloads
