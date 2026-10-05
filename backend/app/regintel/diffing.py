"""条级结构 Diff：两个法规版本的 article 单元对比。

优先做 Article 级 diff（而非整篇文本 diff）：
按规范化的条款号（见 parsing.article_key）对齐，输出
ADDED / MODIFIED / REMOVED / RENUMBERED 四类变化，并给出 materiality 分级。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class UnitChange:
    """一条法律单元级变化。"""

    change_type: str  # ADDED / MODIFIED / REMOVED / RENUMBERED
    unit_number: str  # 新版本的条款号（REMOVED 时为旧条款号）
    old_text: str = ""
    new_text: str = ""
    old_unit_number: str = ""  # RENUMBERED 时的旧条款号
    similarity: float = 1.0  # MODIFIED 时的文本相似度
    materiality: str = "LOW"


def _similarity(a: str, b: str) -> float:
    """两段文本的相似度（0-1），用于 MODIFIED 变化的重要性分级。"""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


#: 修改片段中出现即提升重要性的强义务关键词
_STRONG_MARKERS = ("同意", "应当", "不得", "必须", "禁止", "consent", "shall", "prohibit")


def _changed_fragments(old: str, new: str, context: int = 8) -> str:
    """提取两文本之间的差异片段（插入/删除/替换部分，带前后少量上下文）。

    上下文窗口用于捕获「同意 → 明示同意」这类紧贴关键词的修改。
    """
    matcher = difflib.SequenceMatcher(None, old, new)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            parts.append(old[max(0, i1 - context) : i2 + context] + new[max(0, j1 - context) : j2 + context])
    return "".join(parts)


def _materiality(change_type: str, similarity: float, fragments: str = "") -> str:
    """确定性重要性分级规则。"""
    if change_type == "REMOVED":
        return "HIGH"
    if change_type == "ADDED":
        return "MEDIUM"
    if change_type == "RENUMBERED":
        return "LOW"
    # MODIFIED：按文本相似度分级（法律文本一字之差也可能重大，阈值从严）；
    # 差异片段触及强义务关键词（同意/应当/不得…）时至少 MEDIUM
    if similarity >= 0.995 and not any(m in fragments for m in _STRONG_MARKERS):
        return "LOW"
    if similarity >= 0.8:
        return "MEDIUM"
    return "HIGH"


def diff_articles(
    old_articles: dict[str, tuple[str, str]],
    new_articles: dict[str, tuple[str, str]],
) -> list[UnitChange]:
    """对比两版 article 集合，返回条级变化列表（按新版本顺序，REMOVED 排最后）。

    :param old_articles: {article_key: (unit_number, text)}（旧版本）
    :param new_articles: {article_key: (unit_number, text)}（新版本）
    """
    changes: list[UnitChange] = []
    old_keys = set(old_articles)
    new_keys = set(new_articles)

    # 1. 两版都存在的条款：文本一致则无变化，不同则 MODIFIED
    for key in new_keys & old_keys:
        old_number, old_text = old_articles[key]
        number, text = new_articles[key]
        if old_text.strip() == text.strip():
            continue
        sim = _similarity(old_text, text)
        changes.append(
            UnitChange(
                "MODIFIED",
                number,
                old_text=old_text,
                new_text=text,
                similarity=sim,
                materiality=_materiality("MODIFIED", sim, _changed_fragments(old_text, text)),
            )
        )

    # 2. 编号消失/出现的条款中先配对「文本完全相同」者 → RENUMBERED
    old_only = old_keys - new_keys
    new_only = new_keys - old_keys
    renumbered_old: set[str] = set()
    renumbered_new: set[str] = set()
    for old_key in sorted(old_only):
        old_number, old_text = old_articles[old_key]
        match = next(
            (k for k in sorted(new_only) if k not in renumbered_new
             and new_articles[k][1].strip() == old_text.strip()),
            None,
        )
        if match is not None:
            renumbered_old.add(old_key)
            renumbered_new.add(match)
            changes.append(
                UnitChange(
                    "RENUMBERED",
                    new_articles[match][0],
                    old_text=old_text,
                    new_text=new_articles[match][1],
                    old_unit_number=old_number,
                    materiality=_materiality("RENUMBERED", 1.0),
                )
            )

    # 3. 剩余：新出现 → ADDED；消失 → REMOVED
    for key in sorted(new_only - renumbered_new):
        number, text = new_articles[key]
        changes.append(
            UnitChange("ADDED", number, new_text=text, materiality=_materiality("ADDED", 0.0))
        )
    for key in sorted(old_only - renumbered_old):
        number, text = old_articles[key]
        changes.append(
            UnitChange("REMOVED", number, old_text=text, materiality=_materiality("REMOVED", 0.0))
        )
    return changes
