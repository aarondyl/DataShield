"""法规文本条款切分。

规则：
1. 按条款标题正则（中文「第X条」/ 英文 "Article N"）切分为条款；
2. 单条超过约 800 字时按段落做二级切分，保持每个片段不超过限制；
   同一条款的多个片段共用同一个 article_number（证据引用不受影响）。
"""

from __future__ import annotations

import re

#: 条款标题：支持中文数字/阿拉伯数字/全角数字的「第X条」，以及 "Article 9" / "Article 9a"
ARTICLE_HEADER = re.compile(
    r"(第[0-9０-９一二三四五六七八九十百千零〇两]+条|Article\s+\d+[A-Za-z]?)",
    re.IGNORECASE,
)

#: 单条条款的最大长度（字符），超过则按段落二级切分
MAX_ARTICLE_LEN = 800

#: 首个条款标题之前的引言超过该长度时，作为「前言」条款保留
_MIN_PREAMBLE_LEN = 100


def split_into_articles(text: str) -> list[dict[str, str]]:
    """把法规全文切分为条款列表。

    :param text: 法规纯文本（txt/md 解码后或 PDF 提取文本）
    :return: [{"article_number": "第九条", "title": "...", "content": "..."}, ...]
             content 含条款标题行，保证每个片段自带「第X条」上下文；
             文本中识别不到条款结构时返回空列表（由调用方报错提示）。
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    matches = list(ARTICLE_HEADER.finditer(text))
    if not matches:
        return []

    articles: list[dict[str, str]] = []

    # 引言（第一章/目录等说明文字），足够长时保留为一个条款
    preamble = text[: matches[0].start()].strip()
    if len(preamble) > _MIN_PREAMBLE_LEN:
        for part in _split_long(preamble):
            articles.append({"article_number": "前言", "title": "", "content": part})

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        header = match.group(0)
        rest = block[match.end() - start :].strip()

        # 标题：条款号之后第一行的剩余部分（如「第九条 特殊类别个人信息的处理」）
        if "\n" in rest:
            title, _, body = rest.partition("\n")
        else:
            title, body = rest, ""
        title = title.strip(" ：:，,。\t")[:80]
        body = body.strip()

        # content 统一携带条款号与标题，保证长条款切分后的首个片段仍含完整上下文
        full = f"{header} {title}\n{body}".strip() if body else f"{header} {title}".strip()
        for part in _split_long(full):
            articles.append({"article_number": header, "title": title, "content": part})

    return articles


def _split_long(text: str, max_len: int = MAX_ARTICLE_LEN) -> list[str]:
    """按段落把超长文本切分为不超过 max_len 的片段（单段超长时硬切）。"""
    if len(text) <= max_len:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 1 > max_len:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
        # 单个段落自身超长：按 max_len 硬切
        while len(current) > max_len:
            chunks.append(current[:max_len])
            current = current[max_len:]
    if current:
        chunks.append(current)
    return chunks or [text]
