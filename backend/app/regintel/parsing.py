"""法律结构解析：把规范化法规文本拆成 chapter / section / article / paragraph 结构树。

支持两类解析器：
- ``cn_law``：中国法律（第X章 / 第X节 / 第X条 / 款），自动跳过卷首目录；
- ``gdpr_bilingual``：GDPR 中英对照文本（CHAPTER / Section / Article + 双语标题）。

解析结果为扁平的 :class:`ParsedUnit` 列表（带 ``parent_index`` 指回父单元在列表中的下标），
由入库流水线落成 ``legal_units`` 表的树结构。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: 中文数字字符集（条号支持「第六十六条之一」形式）
_CN_NUM = "〇零一二三四五六七八九十百千两"

_RE_CN_CHAPTER = re.compile(rf"^(第[{_CN_NUM}0-9]+章)\s*(.*)$")
_RE_CN_SECTION = re.compile(rf"^(第[{_CN_NUM}0-9]+节)\s*(.*)$")
_RE_CN_ARTICLE = re.compile(rf"^(第[{_CN_NUM}0-9]+条(?:之[{_CN_NUM}0-9]+)?)\s*(.*)$")
_RE_CN_TOC = re.compile(r"^目\s*录$")
#: 中文汉字之间的空格（「总 则」→「总则」）
_RE_CJK_SPACE = re.compile(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])")

_RE_GDPR_CHAPTER = re.compile(r"^CHAPTER\s+([IVXLC]+)\s*[-·:]?\s*(.*)$")
_RE_GDPR_SECTION = re.compile(r"^Section\s+(\d+)\s*[-·:]?\s*(.*)$")
_RE_GDPR_ARTICLE = re.compile(r"^Article\s+(\d+[a-zA-Z]?)\s*[-·:]?\s*(.*)$")


def _is_gdpr_heading(m: re.Match[str] | None) -> bool:
    """GDPR 标题行必须含双语分隔符「 / 」，否则视为正文中的条文引用。"""
    return m is not None and " / " in m.group(2)


@dataclass
class ParsedUnit:
    """解析出的一个法律结构单元（扁平形式，parent_index 指向父单元在列表中的下标）。"""

    unit_type: str  # chapter / section / article / paragraph
    unit_number: str = ""
    heading: str = ""
    text: str = ""
    path: str = ""
    order_index: int = 0
    parent_index: int | None = None
    paragraphs: list[str] = field(default_factory=list)  # article 的下级款项原文（按顺序）


def cn_number_to_int(text: str) -> int | None:
    """把中文数字（如「七十四」「一百零三」）转成整数；无法解析返回 None。"""
    digits = {"〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if all(ch in digits for ch in text):
        value = 0
        for ch in text:  # 纯数字逐位（罕见，如「二〇二一」）
            value = value * 10 + digits[ch]
        return value
    total, section = 0, 0
    for ch in text:
        if ch in digits:
            section = digits[ch]
        elif ch == "十":
            section = section if section else 1
            total += section * 10
            section = 0
        elif ch == "百":
            section = section if section else 1
            total += section * 100
            section = 0
        elif ch == "千":
            section = section if section else 1
            total += section * 1000
            section = 0
        else:
            return None
    return total + section


def article_key(unit_number: str) -> str:
    """把条款号规范成跨版本可比较的 key。

    - 「第十三条」→ ``13``；「第六十六条之一」→ ``66-1``；
    - ``Article 13`` → ``13``；``Article 13a`` → ``13a``。
    """
    num = unit_number.strip()
    m = re.match(rf"^第([{_CN_NUM}0-9]+)条(?:之([{_CN_NUM}0-9]+))?$", num)
    if m:
        base = cn_number_to_int(m.group(1))
        if base is not None:
            suffix = cn_number_to_int(m.group(2)) if m.group(2) else None
            return f"{base}-{suffix}" if suffix is not None else str(base)
        return num
    m = re.match(r"^Article\s+(\d+[a-zA-Z]?)$", num, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return num.lower()


def parse_legal_text(text: str, parser_type: str) -> list[ParsedUnit]:
    """按 parser_type 解析法规文本，返回扁平单元列表（order_index 按出现顺序）。"""
    if parser_type == "gdpr_bilingual":
        units = _parse_gdpr_bilingual(text)
    else:
        units = _parse_cn_law(text)
    for i, unit in enumerate(units):
        unit.order_index = i
    return units


def article_units(units: list[ParsedUnit]) -> list[ParsedUnit]:
    """过滤出 article 级单元（diff / requirement / chunking 的工作粒度）。"""
    return [u for u in units if u.unit_type == "article"]


# ---------------------------------------------------------------------------
# 中国法律解析
# ---------------------------------------------------------------------------


def _strip_toc(lines: list[str]) -> list[str]:
    """跳过卷首目录。

    目录与正文的章/节标题行在外观上无法区分，但正文一定以「第一章」重新开始
    且紧随其后就是第一条。取第一条之前最近一个「第一章」作为正文起点。
    """
    toc_idx = next((i for i, line in enumerate(lines[:20]) if _RE_CN_TOC.match(line)), None)
    if toc_idx is None:
        return lines
    first_article = next(
        (i for i in range(toc_idx + 1, len(lines)) if _RE_CN_ARTICLE.match(lines[i])), None
    )
    if first_article is None:
        return lines
    # 第一条之前紧邻的章/节标题行游标（含目录项与正文标题）
    start = first_article
    while start > toc_idx + 1 and (
        _RE_CN_CHAPTER.match(lines[start - 1]) or _RE_CN_SECTION.match(lines[start - 1])
    ):
        start -= 1
    # 在该游标范围内取最后一个「第一章」，即正文的第一章
    for i in range(first_article - 1, start - 1, -1):
        m = _RE_CN_CHAPTER.match(lines[i])
        if m and m.group(1) in ("第一章", "第1章"):
            return lines[i:]
    return lines[start:]


def _parse_cn_law(text: str) -> list[ParsedUnit]:
    """解析中国法律文本（章 / 节 / 条 / 款四级）。"""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    lines = _strip_toc(lines)

    units: list[ParsedUnit] = []
    chapter: ParsedUnit | None = None
    section: ParsedUnit | None = None
    article: ParsedUnit | None = None

    def flush_article() -> None:
        nonlocal article
        if article is not None:
            parts = [article.text, *article.paragraphs]
            article.text = "\n".join(p for p in parts if p).strip()
            units.append(article)
            article = None

    for line in lines:
        m = _RE_CN_CHAPTER.match(line)
        if m:
            flush_article()
            heading = _RE_CJK_SPACE.sub("", m.group(2))
            chapter = ParsedUnit("chapter", unit_number=m.group(1), heading=heading)
            chapter.path = chapter.unit_number
            units.append(chapter)
            section = None
            continue
        m = _RE_CN_SECTION.match(line)
        if m:
            flush_article()
            heading = _RE_CJK_SPACE.sub("", m.group(2))
            section = ParsedUnit("section", unit_number=m.group(1), heading=heading)
            section.parent_index = id(chapter) if chapter is not None else None
            section.path = f"{chapter.path}/{section.unit_number}" if chapter else section.unit_number
            units.append(section)
            continue
        m = _RE_CN_ARTICLE.match(line)
        if m:
            flush_article()
            parent = section or chapter
            article = ParsedUnit("article", unit_number=m.group(1), text=m.group(2).strip())
            article.parent_index = id(parent) if parent is not None else None
            article.path = f"{parent.path}/{article.unit_number}" if parent else article.unit_number
            continue
        # 普通行：属于当前条的款；尚无任何条则视为前言忽略
        if article is not None:
            article.paragraphs.append(line)
    flush_article()
    return _attach_paragraph_units(units)


def _attach_paragraph_units(units: list[ParsedUnit]) -> list[ParsedUnit]:
    """把 article 的 paragraphs 展开为 paragraph 子单元（紧跟 article 之后）。"""
    id_to_index: dict[int, int] = {}
    result: list[ParsedUnit] = []
    for unit in units:
        # parent_index 暂存父单元的 id()，此处换算为结果列表下标
        parent = unit.parent_index
        unit.parent_index = id_to_index.get(parent) if parent is not None else None
        id_to_index[id(unit)] = len(result)
        result.append(unit)
        if unit.unit_type == "article" and len(unit.paragraphs) > 1:
            for i, para in enumerate(unit.paragraphs, start=1):
                child = ParsedUnit("paragraph", unit_number=str(i), text=para)
                child.parent_index = len(result) - 1
                child.path = f"{unit.path}/款{i}"
                result.append(child)
    return result


# ---------------------------------------------------------------------------
# GDPR 中英对照解析
# ---------------------------------------------------------------------------


def _split_bilingual(rest: str) -> tuple[str, str]:
    """把「English title / 中文标题」拆成 (英文, 中文)；无分隔符时整体视为英文。"""
    if " / " in rest:
        en, zh = rest.rsplit(" / ", 1)
        return en.strip(), zh.strip()
    return rest.strip(), ""


def _parse_gdpr_bilingual(text: str) -> list[ParsedUnit]:
    """解析 GDPR 中英对照文本（CHAPTER / Section / Article + 双语标题，正文按行成款）。"""
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    units: list[ParsedUnit] = []
    chapter: ParsedUnit | None = None
    section: ParsedUnit | None = None
    article: ParsedUnit | None = None

    def flush_article() -> None:
        nonlocal article
        if article is not None:
            article.text = "\n".join(p for p in article.paragraphs if p).strip()
            units.append(article)
            article = None

    for line in lines:
        m = _RE_GDPR_CHAPTER.match(line)
        if _is_gdpr_heading(m):
            flush_article()
            en, zh = _split_bilingual(m.group(2))
            heading = f"{en} / {zh}" if zh else en
            chapter = ParsedUnit("chapter", unit_number=f"CHAPTER {m.group(1).upper()}", heading=heading)
            chapter.path = chapter.unit_number
            units.append(chapter)
            section = None
            continue
        m = _RE_GDPR_SECTION.match(line)
        if _is_gdpr_heading(m):
            flush_article()
            en, zh = _split_bilingual(m.group(2))
            heading = f"{en} / {zh}" if zh else en
            section = ParsedUnit("section", unit_number=f"Section {m.group(1)}", heading=heading)
            section.parent_index = id(chapter) if chapter is not None else None
            section.path = f"{chapter.path}/{section.unit_number}" if chapter else section.unit_number
            units.append(section)
            continue
        m = _RE_GDPR_ARTICLE.match(line)
        if _is_gdpr_heading(m):
            flush_article()
            en, zh = _split_bilingual(m.group(2))
            heading = f"{en} / {zh}" if zh else en
            article = ParsedUnit("article", unit_number=f"Article {m.group(1)}", heading=heading)
            parent = section or chapter
            article.parent_index = id(parent) if parent is not None else None
            article.path = f"{parent.path}/{article.unit_number}" if parent else article.unit_number
            continue
        # 正文行：英文原文段与中文译文段均按行成款
        if article is not None:
            article.paragraphs.append(line)
    flush_article()
    return _attach_paragraph_units(units)
