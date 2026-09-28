# -*- coding: utf-8 -*-
"""整改路线图模块。

把规则引擎命中的风险按严重度映射为 7 天 / 30 天 / 90 天三档整改计划：
    🔴 高风险 -> 7 天内（立即处理）
    🟡 中风险 -> 30 天内（近期完成）
    🟢 低风险 -> 90 天内（持续优化）
勾选进度由 app.py 存放在 st.session_state 中。
"""

from rules import LEVEL_EMOJI

# 风险等级 -> 整改阶段
STAGE_BY_LEVEL = {
    "高": {"stage": "🚨 7 天内（立即整改）", "days": 7},
    "中": {"stage": "⚠️ 30 天内（近期完成）", "days": 30},
    "低": {"stage": "💡 90 天内（持续优化）", "days": 90},
}

STAGE_ORDER = ["🚨 7 天内（立即整改）", "⚠️ 30 天内（近期完成）", "💡 90 天内（持续优化）"]


def build_roadmap(hits):
    """按整改阶段分组命中项。

    返回：dict，{阶段名: [命中记录...]}，三个阶段始终存在（可能为空列表）。
    """
    roadmap = {s: [] for s in STAGE_ORDER}
    for h in hits:
        roadmap[STAGE_BY_LEVEL[h["level"]]["stage"]].append(h)
    return roadmap


def roadmap_item_key(hit):
    """生成路线图勾选框的稳定 key。"""
    return f"roadmap_done_{hit['rule_id']}"


def summarize_progress(roadmap, done_keys):
    """统计整改完成进度。

    参数：
        roadmap: build_roadmap 的返回值。
        done_keys: set，已勾选完成的 rule_id 集合。

    返回：(已完成数, 总数, 百分比 0-100)。
    """
    total = sum(len(v) for v in roadmap.values())
    done = sum(1 for items in roadmap.values() for h in items if h["rule_id"] in done_keys)
    pct = round(done / total * 100) if total else 0
    return done, total, pct


def stage_of(hit):
    """返回单条命中所属阶段名与 emoji 等级标识。"""
    info = STAGE_BY_LEVEL[hit["level"]]
    return info["stage"], LEVEL_EMOJI[hit["level"]]
