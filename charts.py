# -*- coding: utf-8 -*-
"""可视化图表模块（基于 plotly）。

提供：七维度雷达图、风险分布柱状图、历史得分趋势线。
所有函数只返回 figure 对象，由 app.py 用 st.plotly_chart 渲染。
"""

import plotly.graph_objects as go

from rules import LEVEL_EMOJI

# 全局配色：红/黄/绿风险色系 + 主色
COLOR_HIGH = "#e74c3c"
COLOR_MID = "#f1c40f"
COLOR_LOW = "#2ecc71"
COLOR_MAIN = "#4c8bf5"


def radar_chart(dim_scores):
    """七维度合规得分雷达图。

    参数：dim_scores: dict，{维度名: 0-100 得分}
    """
    dims = list(dim_scores.keys())
    values = list(dim_scores.values())
    # 闭合雷达图（首尾相接）
    fig = go.Figure(go.Scatterpolar(
        r=values + [values[0]],
        theta=dims + [dims[0]],
        fill="toself",
        fillcolor="rgba(76, 139, 245, 0.25)",
        line=dict(color=COLOR_MAIN, width=2),
        marker=dict(size=6),
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[20, 40, 60, 80, 100])),
        showlegend=False,
        margin=dict(l=60, r=60, t=40, b=40),
        height=420,
    )
    return fig


def risk_bar_chart(counts):
    """风险等级分布柱状图。

    参数：counts: dict，{"高": n, "中": n, "低": n}
    """
    labels = [f"{LEVEL_EMOJI[k]} {k}风险" for k in ("高", "中", "低")]
    values = [counts["高"], counts["中"], counts["低"]]
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=[COLOR_HIGH, COLOR_MID, COLOR_LOW],
        text=values, textposition="outside",
    ))
    fig.update_layout(
        yaxis=dict(title="数量", rangemode="tozero", dtick=1),
        margin=dict(l=40, r=40, t=30, b=40),
        height=320,
    )
    return fig


def dimension_bar_chart(dim_scores):
    """七维度得分横向条形图（红色低分警示）。"""
    dims = list(dim_scores.keys())[::-1]
    values = [dim_scores[d] for d in dims]
    colors = [COLOR_HIGH if v < 60 else COLOR_MID if v < 80 else COLOR_LOW for v in values]
    fig = go.Figure(go.Bar(
        x=values, y=dims, orientation="h",
        marker_color=colors, text=values, textposition="outside",
    ))
    fig.update_layout(
        xaxis=dict(title="得分", range=[0, 110]),
        margin=dict(l=40, r=40, t=30, b=40),
        height=360,
    )
    return fig


def history_trend_chart(records):
    """历史自查总分趋势线。

    参数：records: list[dict]，history 模块的记录（含 time/score/rating）。
    """
    times = [r["time"] for r in records]
    scores = [r["score"] for r in records]
    fig = go.Figure(go.Scatter(
        x=times, y=scores, mode="lines+markers+text",
        text=scores, textposition="top center",
        line=dict(color=COLOR_MAIN, width=2), marker=dict(size=8),
    ))
    # 评级参考线
    fig.add_hline(y=90, line_dash="dot", line_color=COLOR_LOW, annotation_text="优秀线 90")
    fig.add_hline(y=60, line_dash="dot", line_color=COLOR_HIGH, annotation_text="高风险线 60")
    fig.update_layout(
        yaxis=dict(title="总分", range=[0, 105]),
        xaxis=dict(title=""),
        margin=dict(l=40, r=40, t=30, b=40),
        height=360,
    )
    return fig
