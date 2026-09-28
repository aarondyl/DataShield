# -*- coding: utf-8 -*-
"""合规报告生成与导出模块。

负责：计算合规总分与评级、汇总风险项、生成可下载的 Markdown 报告。
评分规则：起始 100 分，命中高风险扣 15 分、中风险扣 8 分、低风险扣 3 分，
下限 0 分。评级：90+ 优秀 / 75-89 良好 / 60-74 待改进 / <60 高风险。
维度得分见 rules.compute_dimension_scores（同一扣分规则按维度独立计算）。
"""

from datetime import datetime

from questionnaire import QUESTIONS
from regulations_data import REGULATIONS
from rules import LEVEL_DEDUCT, LEVEL_EMOJI, summarize_articles

# 布尔答案的中文展示
YES_NO = {True: "是", False: "否", None: "（未涉及）"}


def format_answer(key, value):
    """把问卷答案格式化为中文展示文本。"""
    if isinstance(value, bool) or value is None:
        return YES_NO[value]
    if isinstance(value, list):
        return "、".join(value) if value else "（未选择）"
    return str(value)


def compute_score(hits):
    """按命中风险计算总分：100 起始，高 -15 / 中 -8 / 低 -3，下限 0 分。"""
    score = 100 - sum(LEVEL_DEDUCT[h["level"]] for h in hits)
    return max(0, score)


def compute_rating(score):
    """按总分给出评级：90+ 优秀 / 75-89 良好 / 60-74 待改进 / <60 高风险。"""
    if score >= 90:
        return "优秀"
    if score >= 75:
        return "良好"
    if score >= 60:
        return "待改进"
    return "高风险"


def level_counts(hits):
    """统计各风险等级的命中数量，返回 dict，如 {"高": 1, "中": 2, "低": 1}。"""
    counts = {"高": 0, "中": 0, "低": 0}
    for h in hits:
        counts[h["level"]] += 1
    return counts


def answers_review_lines(answers):
    """按问卷模块整理答案回顾（Markdown 行列表），app 页面与报告共用。"""
    lines = []
    current_module = None
    for q in QUESTIONS:
        visible = q.get("show_if", lambda a: True)(answers)
        if not visible:
            continue  # 动态追问中未触发的题目不展示
        if q["module"] != current_module:
            current_module = q["module"]
            lines.append(f"\n**{current_module}**")
        lines.append(f"- {q['text']}：{format_answer(q['key'], answers.get(q['key']))}")
    return lines


def build_markdown_report(answers, hits, score, rating, dim_scores=None, explanations=None):
    """生成 Markdown 格式的结构化合规报告（用于 st.download_button 导出）。

    参数：
        answers: dict，问卷答案。
        hits: list[dict]，规则引擎命中的风险记录。
        score: int，合规总分。 rating: str，评级。
        dim_scores: dict 或 None，七维度得分（rules.compute_dimension_scores 的结果）。
        explanations: dict 或 None，{规则ID: 解释文本}（AI/模板解释，可选）。

    返回：str，Markdown 文本。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    counts = level_counts(hits)
    lines = [
        "# 数盾 DataShield 合规自查报告",
        "",
        f"- 生成时间：{now}",
        f"- 合规总分：**{score} / 100**",
        f"- 综合评级：**{rating}**",
        f"- 风险分布：🔴 高 {counts['高']} 项 / 🟡 中 {counts['中']} 项 / 🟢 低 {counts['低']} 项",
        "",
        "> 本报告由自动化工具生成，仅供参考，不构成法律意见。",
        "",
        "---",
        "",
        "## 一、问卷答案回顾",
    ]
    lines += answers_review_lines(answers)

    if dim_scores:
        lines += [
            "",
            "---",
            "",
            "## 二、维度得分",
            "",
        ]
        for dim, s in dim_scores.items():
            lines.append(f"- {dim}：{s} / 100")

    lines += [
        "",
        "---",
        "",
        "## 三、命中的风险项与整改建议",
        "",
    ]
    for i, h in enumerate(hits, 1):
        article_names = "、".join(
            f"{REGULATIONS[a]['law']}{REGULATIONS[a]['article']}"
            for a in h["articles"] if a in REGULATIONS
        )
        lines += [
            f"### {i}. {LEVEL_EMOJI[h['level']]} {h['level']}风险 — {h['risk']}",
            "",
            f"- 命中规则：{h['rule_id']}（维度：{h.get('dimension', '-')}）",
            f"- 命中条件：{h['condition']}",
            f"- 违反法条：{article_names}",
            f"- 整改建议：{h['advice']}",
        ]
        if explanations and h["rule_id"] in explanations:
            lines += ["", "**详细解释**：", "", explanations[h["rule_id"]]]
        lines.append("")

    lines += [
        "---",
        "",
        "## 四、涉及法条摘要",
        "",
    ]
    for aid in summarize_articles(hits):
        item = REGULATIONS.get(aid)
        if item:
            lines.append(f"- **{item['law']}{item['article']}**：{item['summary']}")

    lines += [
        "",
        "---",
        "",
        "*数盾 DataShield — 面向中小开发者的数据合规自查工具（仅供参考，不构成法律意见）*",
    ]
    return "\n".join(lines)
