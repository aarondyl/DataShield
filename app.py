# -*- coding: utf-8 -*-
"""数盾 DataShield — Streamlit 主入口。

面向中小 App 开发者和网站主的数据合规自查工具，对照
GDPR（欧盟《通用数据保护条例》）、中国《数据安全法》《个人信息保护法》。

页面结构（侧边栏导航）：
    1. 首页            工具说明与使用流程
    2. 文档智能分析    上传计划书或粘贴文本，自动预填问卷
    3. 合规自查问卷    六个模块的问题，含追问和行业预设
    4. 合规仪表盘      雷达图、维度得分、风险分布、案例警示
    5. 整改路线图      7/30/90 天整改计划，可勾选进度
    6. 合规报告        总分与评级、汇总表、Markdown 下载
    7. 隐私政策生成    按问卷答案生成隐私政策初稿
    8. 隐私政策体检    检查现有政策是否缺少法定必备要素
    9. 历史趋势        多次自查得分对比
    10. 法条与案例     法条检索和处罚案例

运行方式：streamlit run app.py
"""

import pandas as pd
import streamlit as st

from cases_data import CASES, cases_for_dimensions
from charts import dimension_bar_chart, history_trend_chart, radar_chart, risk_bar_chart
from doc_analyzer import analyze, extract_text
from history import clear_records, compare_with_last, list_records, save_record
from llm_explainer import explain_risk, is_llm_available, review_policy_text, polish_policy
from policy_checker import check_policy
from policy_generator import generate_policy
from presets import PRESETS
from questionnaire import QUESTION_MODULES, QUESTIONS, default_answers, normalize_answers
from regulations_data import REGULATIONS
from report import (
    answers_review_lines,
    build_markdown_report,
    compute_rating,
    compute_score,
    level_counts,
)
from roadmap import build_roadmap, roadmap_item_key, summarize_progress
from rules import DIMENSIONS, LEVEL_EMOJI, compute_dimension_scores, evaluate_rules

# 页面全局配置
st.set_page_config(page_title="数盾 DataShield · 合规自查", page_icon="🛡️", layout="wide")

# 评级标识
RATING_COLOR = {"优秀": "🟢", "良好": "🟢", "待改进": "🟡", "高风险": "🔴"}


# ---------------- 公共函数 ----------------
def _hits_to_dataframe(hits):
    """把命中记录整理成结果表格（风险等级带标识，已按严重度排序）。"""
    rows = []
    for h in hits:
        article_names = "、".join(
            f"{REGULATIONS[a]['law']}{REGULATIONS[a]['article']}"
            for a in h["articles"] if a in REGULATIONS
        )
        rows.append({
            "风险等级": f"{LEVEL_EMOJI[h['level']]} {h['level']}",
            "规则": h["rule_id"],
            "维度": h.get("dimension", "-"),
            "风险描述": h["risk"],
            "违反法条": article_names,
            "整改建议": h["advice"],
        })
    return pd.DataFrame(rows)


def _render_hit_detail(h, use_ai):
    """在 expander 中展示单条命中规则的详细说明（含法条摘要与可选 AI 解释）。"""
    st.markdown(f"**命中条件**：{h['condition']}")
    st.markdown(f"**整改建议**：{h['advice']}")
    st.markdown("**违反法条**：")
    for aid in h["articles"]:
        item = REGULATIONS.get(aid)
        if item:
            st.markdown(f"- {item['law']}{item['article']}：{item['summary']}")

    if use_ai:
        # 解释结果缓存在 session_state，避免页面重绘时重复调用
        if h["rule_id"] not in st.session_state.explanations:
            with st.spinner(f"正在生成 {h['rule_id']} 的详细解释…"):
                st.session_state.explanations[h["rule_id"]] = explain_risk(h)
        res = st.session_state.explanations[h["rule_id"]]
        source = "AI 生成" if res["source"] == "llm" else "内置模板（未配置 Key 或调用失败时使用）"
        st.markdown(f"**详细解释**（来源：{source}）：")
        st.info(res["text"])


def _require_hits():
    """取 session_state 中的评估结果；没有则提示并返回 None。"""
    hits = st.session_state.get("hits")
    if not hits:
        st.info("请先在「合规自查问卷」页完成问卷并点击「生成评估结果」。")
        return None
    return hits


def _apply_answers(new_answers):
    """把预设/预填答案写入会话，并清除旧控件状态，确保问卷按新答案重新渲染。

    Streamlit 的带 key 控件一旦创建，显示值以控件状态为准（忽略 index 参数），
    所以必须同时清掉 q_* 控件键，否则预设加载后页面仍显示旧选项。
    """
    st.session_state.answers = normalize_answers(new_answers)
    for q in QUESTIONS:
        st.session_state.pop(f"q_{q['key']}", None)
    st.session_state.prefill_applied = True


# ---------------- 页面 1：首页 ----------------
def page_home():
    st.title("🛡️ 数盾 DataShield")
    st.markdown("**中小开发者的数据合规自查工具**")
    st.markdown(
        "对照 GDPR（欧盟《通用数据保护条例》）、中国《数据安全法》《个人信息保护法》，"
        "通过问卷和规则引擎检查产品在数据处理上的常见违规点，并给出整改建议。"
    )

    st.markdown("#### 主要功能")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            "- **文档智能分析**：上传项目计划书或粘贴文本，自动预填问卷\n"
            "- **合规自查问卷**：六个模块的问题，按回答自动追问细节\n"
            "- **合规仪表盘**：七维度得分雷达图、风险分布、案例警示\n"
            "- **整改路线图**：按轻重缓急生成 7/30/90 天整改清单\n"
            "- **历史趋势**：保存每次自查结果，对比整改前后得分"
        )
    with col2:
        st.markdown(
            "- **合规报告**：总分与评级，可下载 Markdown 报告\n"
            "- **隐私政策生成**：按问卷答案生成政策初稿\n"
            "- **隐私政策体检**：检查现有政策是否缺少法定要素\n"
            "- **法条与案例**：59 组法条摘要检索、16 个处罚案例\n"
            "- **行业预设**：电商、社交、教育、医疗等典型场景一键加载"
        )

    st.divider()
    st.markdown("**使用顺序**：文档智能分析（可选）→ 合规自查问卷 → 合规仪表盘 → 整改路线图 → 合规报告")
    st.warning("免责声明：本工具依据公开法条和预设规则生成结果，仅供参考，不构成法律意见。"
               "涉及重大数据处理决策时，请咨询专业律师。")
    if is_llm_available():
        st.success("已配置 DEEPSEEK_API_KEY：文档分析、详细解释等功能使用 AI 生成。")
    else:
        st.info("未配置 DEEPSEEK_API_KEY：全部功能可正常使用，解释与文档分析由内置模板和规则完成。")


# ---------------- 页面 2：文档智能分析 ----------------
def _run_doc_analysis(text):
    """执行文档分析并把结果写入会话（上传与粘贴两个入口共用）。"""
    with st.spinner("正在分析文档内容…"):
        st.session_state.doc_text = text
        st.session_state.doc_result = analyze(text)


def page_doc_analysis():
    st.title("文档智能分析")
    st.markdown(
        "把项目计划书、需求文档或产品介绍交给系统分析，识别其中涉及的数据处理行为，"
        "自动给出问卷预填建议。分析结果只是参考，请在问卷页逐项确认后再生成评估结果。"
    )

    tab_file, tab_text = st.tabs(["上传文件", "粘贴文本"])
    with tab_file:
        uploaded = st.file_uploader(
            "支持 .txt / .md / .docx / .pdf", type=["txt", "md", "docx", "pdf"])
        if uploaded:
            st.caption(f"已选择：{uploaded.name}（{uploaded.size / 1024:.1f} KB）")
        if st.button("分析上传的文件", type="primary", disabled=not uploaded):
            try:
                with st.spinner("正在解析文档…"):
                    text = extract_text(uploaded)
                if len(text.strip()) < 50:
                    st.warning("提取到的文本过少（可能是扫描件或空文档），请换文件或改用粘贴文本。")
                else:
                    _run_doc_analysis(text)
            except Exception as e:
                st.error(f"文档解析失败：{e}")
    with tab_text:
        pasted = st.text_area("把文档内容粘贴到这里", height=200,
                              placeholder="例如：本 App 需要手机号注册，接入第三方广告 SDK，数据存储在境内服务器……")
        if st.button("分析粘贴的文本", disabled=len(pasted.strip()) < 20):
            _run_doc_analysis(pasted)

    result = st.session_state.get("doc_result")
    if not result:
        return

    st.divider()
    text_len = len(st.session_state.get("doc_text", ""))
    mode_name = "AI 通读" if result["mode"] == "llm" else "关键词规则"
    st.success(f"分析完成（方式：{mode_name}，提取文本 {text_len} 字）。{result['note']}")

    suggestions = result["suggestions"]
    if not suggestions:
        st.warning("未从文档中识别出与问卷相关的信息，建议直接到问卷页手动填写。")
        return

    # 展示识别结果（启发式模式附匹配依据，便于核对可靠性）
    q_index = {q["key"]: q for q in QUESTIONS}
    evidence = result.get("evidence", {})
    rows = []
    for key, value in suggestions.items():
        q = q_index.get(key)
        if not q:
            continue
        if isinstance(value, bool):
            show = "是" if value else "否"
        elif isinstance(value, list):
            show = "、".join(map(str, value))
        else:
            show = str(value)
        ev = evidence.get(key)
        basis = f"命中「{ev['keyword']}」：{ev['snippet']}" if ev else "AI 通读全文判断"
        rows.append({"问题": q["text"], "预填答案": show, "判断依据": basis})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    if st.button("采纳建议并填入问卷", type="primary"):
        merged = dict(st.session_state.answers)
        merged.update(suggestions)
        _apply_answers(merged)
        st.success("已填入问卷。请从左侧进入「合规自查问卷」逐项核对后生成评估结果。")

    with st.expander("查看提取的文档原文（前 3000 字）"):
        st.text(st.session_state.get("doc_text", "")[:3000])


# ---------------- 页面 3：合规自查问卷 ----------------
def _yesno_widget(q, current):
    """渲染是/否问题，返回 bool 或 None。"""
    idx = {True: 0, False: 1}.get(current)
    choice = st.radio(q["text"], ["是", "否"], index=idx, horizontal=True, key=f"q_{q['key']}")
    return None if choice is None else choice == "是"


def page_questionnaire():
    st.title("合规自查问卷")

    # 行业预设加载
    col1, col2 = st.columns([3, 1])
    preset_name = col1.selectbox("行业预设（选择相近场景一键填入，再按实际情况修改）",
                                 list(PRESETS.keys()))
    if col2.button("加载预设", width="stretch"):
        _apply_answers(dict(PRESETS[preset_name]))
        st.rerun()

    if st.session_state.pop("prefill_applied", False):
        st.success("已填入预置答案，请逐项核对后再生成结果。")

    st.caption("部分问题回答「是」后会展开追问。答案实时生效，填完点击底部按钮生成结果。")

    answers = dict(st.session_state.answers)
    # 逐模块渲染；控件变更会触发 rerun，从而实现动态追问
    for module in QUESTION_MODULES:
        st.markdown(f"### {module}")
        for q in QUESTIONS:
            if q["module"] != module:
                continue
            if not q.get("show_if", lambda a: True)(answers):
                continue  # 追问未触发，跳过本题
            current = answers.get(q["key"])
            if q["type"] == "yesno":
                answers[q["key"]] = _yesno_widget(q, current)
            elif q["type"] == "select":
                idx = q["options"].index(current) if current in q["options"] else None
                answers[q["key"]] = st.selectbox(q["text"], q["options"], index=idx,
                                                 key=f"q_{q['key']}")
            else:  # multiselect
                answers[q["key"]] = st.multiselect(q["text"], q["options"],
                                                   default=current or [], key=f"q_{q['key']}")
        st.divider()

    if st.button("生成评估结果", type="primary", width="stretch"):
        answers = normalize_answers(answers)
        st.session_state.answers = answers
        st.session_state.hits = evaluate_rules(answers)
        st.session_state.explanations = {}
        st.session_state.roadmap_done = set()
        # 自动存档，供历史趋势对比
        score = compute_score(st.session_state.hits)
        save_record(answers, st.session_state.hits, score, compute_rating(score),
                    compute_dimension_scores(st.session_state.hits))
        st.session_state.just_evaluated = True
        st.rerun()

    if st.session_state.pop("just_evaluated", False):
        st.success("评估完成，结果已自动存档。可从左侧进入「合规仪表盘」或「合规报告」查看。")

    # 问卷页内直接预览结果摘要
    hits = st.session_state.get("hits")
    if hits:
        counts = level_counts(hits)
        st.subheader(f"当前结果：🔴 高风险 {counts['高']} 项　🟡 中风险 {counts['中']} 项　🟢 低风险 {counts['低']} 项")
        st.dataframe(_hits_to_dataframe(hits), width="stretch", hide_index=True)


# ---------------- 页面 4：合规仪表盘 ----------------
def page_dashboard():
    st.title("合规仪表盘")
    hits = _require_hits()
    if not hits:
        return

    score = compute_score(hits)
    rating = compute_rating(score)
    dim_scores = compute_dimension_scores(hits)
    counts = level_counts(hits)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("合规总分", f"{score} / 100")
    col2.metric("综合评级", f"{RATING_COLOR[rating]} {rating}")
    col3.metric("🔴 高风险", f"{counts['高']} 项")
    col4.metric("🟡 中风险", f"{counts['中']} 项")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 七维度雷达图")
        st.plotly_chart(radar_chart(dim_scores), width="stretch")
    with c2:
        st.markdown("#### 风险等级分布")
        st.plotly_chart(risk_bar_chart(counts), width="stretch")

    st.markdown("#### 维度得分明细")
    st.plotly_chart(dimension_bar_chart(dim_scores), width="stretch")

    # 案例警示：展示与命中维度相关的真实处罚案例
    hit_dims = {h["dimension"] for h in hits if h["level"] in ("高", "中")}
    related = cases_for_dimensions(hit_dims)
    if related:
        st.markdown("#### 相关处罚案例")
        for case in related:
            with st.expander(f"{case['name']} —— {case['fine']}"):
                st.markdown(f"- **时间与机构**：{case['time']} · {case['authority']}")
                st.markdown(f"- **事由**：{case['reason']}")
                st.markdown(f"- **启示**：{case['lesson']}")

    # 命中详情 + 详细解释开关
    st.markdown("#### 命中规则详情")
    use_ai = st.toggle("生成详细解释（配置 API Key 时由 AI 生成，否则用内置模板）", value=False)
    for h in hits:
        with st.expander(f"{LEVEL_EMOJI[h['level']]} {h['rule_id']}｜{h['dimension']}｜{h['condition']}"):
            _render_hit_detail(h, use_ai)


# ---------------- 页面 5：整改路线图 ----------------
def page_roadmap():
    st.title("整改路线图")
    hits = _require_hits()
    if not hits:
        return

    roadmap = build_roadmap(hits)
    done_keys = st.session_state.roadmap_done
    done, total, pct = summarize_progress(roadmap, done_keys)
    st.progress(pct / 100, text=f"整改进度：{done}/{total} 项已完成（{pct}%）")

    for stage, items in roadmap.items():
        st.markdown(f"### {stage}")
        if not items:
            st.caption("（无任务）")
            continue
        for h in items:
            key = roadmap_item_key(h)
            checked = st.checkbox(
                f"{LEVEL_EMOJI[h['level']]} **{h['rule_id']}** {h['condition']} → {h['advice']}",
                value=h["rule_id"] in done_keys, key=key,
            )
            if checked:
                done_keys.add(h["rule_id"])
            else:
                done_keys.discard(h["rule_id"])
    st.caption("勾选状态仅在本次会话内保留。整改完成后建议重新填写问卷验证效果。")


# ---------------- 页面 6：合规报告 ----------------
def page_report():
    st.title("合规报告")
    answers = st.session_state.get("answers")
    hits = _require_hits()
    if not hits:
        return

    score = compute_score(hits)
    rating = compute_rating(score)
    counts = level_counts(hits)
    dim_scores = compute_dimension_scores(hits)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("合规总分", f"{score} / 100")
    # 与上次对比
    last, delta = compare_with_last(score)
    col2.metric("综合评级", f"{RATING_COLOR[rating]} {rating}",
                delta=None if delta is None else f"{delta:+d} 分（较上次）")
    col3.metric("🔴 高风险", f"{counts['高']} 项")
    col4.metric("🟡 中风险", f"{counts['中']} 项")

    if score >= 90:
        st.success(f"评级「{rating}」：合规状况良好，请保持并定期复查。")
    elif score >= 75:
        st.success(f"评级「{rating}」：整体合规，少量低风险事项建议完善。")
    elif score >= 60:
        st.warning(f"评级「{rating}」：存在中风险事项，建议尽快整改。")
    else:
        st.error(f"评级「{rating}」：存在高风险违规情形，请立即按整改建议处理。")

    with st.expander("问卷答案回顾"):
        for line in answers_review_lines(answers):
            st.markdown(line)

    st.markdown("#### 风险与整改建议汇总")
    st.dataframe(_hits_to_dataframe(hits), width="stretch", hide_index=True)

    explanations = {
        rid: res["text"] for rid, res in st.session_state.get("explanations", {}).items()
    } or None
    md = build_markdown_report(answers, hits, score, rating, dim_scores, explanations)
    st.download_button(
        "下载 Markdown 格式报告",
        data=md.encode("utf-8-sig"),  # 带 BOM，Windows 记事本/Office 打开不乱码
        file_name="datacheck_compliance_report.md",
        mime="text/markdown",
        type="primary",
    )
    st.caption("每次生成评估结果时已自动存档到「历史趋势」。本报告仅供参考，不构成法律意见。")


# ---------------- 页面 7：隐私政策生成 ----------------
def page_policy_generator():
    st.title("隐私政策生成")
    st.markdown("根据当前问卷答案生成隐私政策初稿，替换文中的【占位符】后即可作为工作底稿。")

    col1, col2, col3 = st.columns(3)
    app_name = col1.text_input("产品名称", "我的App")
    company = col2.text_input("公司/团队名称", "【公司名称】")
    contact = col3.text_input("联系邮箱", "privacy@example.com")

    answers = st.session_state.get("answers") or default_answers()
    if not st.session_state.get("hits"):
        st.caption("尚未完成问卷，当前按默认答案演示；完成问卷后生成的内容会更贴合实际情况。")

    if st.button("生成隐私政策", type="primary", width="stretch"):
        st.session_state.policy_text = generate_policy(answers, app_name, company, contact)

    policy = st.session_state.get("policy_text")
    if not policy:
        return

    if is_llm_available() and st.button("AI 润色（可选）"):
        with st.spinner("润色中…"):
            polished = polish_policy(policy)
        if polished:
            st.session_state.policy_text = polished
            st.rerun()
        else:
            st.warning("AI 润色失败，已保留原有内容。")

    st.markdown(policy)
    st.download_button(
        "下载隐私政策（Markdown）",
        data=policy.encode("utf-8-sig"),
        file_name="privacy_policy.md",
        mime="text/markdown",
    )
    st.caption("初稿仅供参考，发布前请核对全部【占位符】，必要时咨询专业律师。")


# ---------------- 页面 8：隐私政策体检 ----------------
def page_policy_checker():
    st.title("隐私政策体检")
    st.markdown("粘贴现有的隐私政策全文，检查 12 项法定必备要素的覆盖情况。")

    text = st.text_area("隐私政策全文", height=220,
                        placeholder="把隐私政策全文粘贴到这里…")
    if st.button("开始体检", type="primary") and text.strip():
        st.session_state.policy_check = check_policy(text)
        st.session_state.policy_check_text = text

    result = st.session_state.get("policy_check")
    if not result:
        return

    col1, col2 = st.columns(2)
    col1.metric("要素覆盖率", f"{result['coverage']}%（{result['covered']}/{result['total']}）")
    col2.progress(result["coverage"] / 100)

    rows = [{
        "要素": i["name"],
        "状态": "✅ 已覆盖" if i["covered"] else "❌ 缺失",
        "命中关键词": "、".join(i["matched"]) if i["matched"] else "-",
        "要求说明": i["hint"],
    } for i in result["items"]]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    missing = [i for i in result["items"] if not i["covered"]]
    if missing:
        st.warning("缺失要素：" + "、".join(i["name"] for i in missing) +
                   "。建议补充后重新体检，或到「隐私政策生成」页重新生成。")
    else:
        st.success("12 项要素全部覆盖，仍建议人工核对表述是否准确。")

    if is_llm_available() and st.toggle("AI 深度复核（按语义检查表述是否到位）", value=False):
        with st.spinner("复核中…"):
            review = review_policy_text(st.session_state.get("policy_check_text", ""))
        if review:
            st.info(review)
        else:
            st.warning("AI 复核调用失败，以上关键词体检结果仍然有效。")


# ---------------- 页面 9：历史趋势 ----------------
def page_history():
    st.title("历史趋势")
    records = list_records()
    if not records:
        st.info("暂无历史记录。在「合规自查问卷」页生成评估结果后会自动存档。")
        return

    if len(records) >= 2:
        st.plotly_chart(history_trend_chart(records), width="stretch")
    else:
        st.info("只有 1 条记录，至少 2 条后展示趋势图。")

    rows = [{
        "时间": r["time"],
        "总分": r["score"],
        "评级": f"{RATING_COLOR.get(r['rating'], '')} {r['rating']}",
        "行业": r.get("industry", "-"),
        "🔴 高": r["counts"]["高"],
        "🟡 中": r["counts"]["中"],
        "🟢 低": r["counts"]["低"],
        "命中规则": "、".join(r.get("rule_ids", [])),
    } for r in reversed(records)]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    if st.button("清空历史记录"):
        clear_records()
        st.rerun()
    st.caption("历史保存在本地文件 .datacheck_history.json 中，最多保留 50 条。")


# ---------------- 页面 10：法条与案例 ----------------
def page_laws_cases():
    st.title("法条与案例")
    tab_law, tab_case = st.tabs(["法条速查", "处罚案例库"])

    with tab_law:
        keyword = st.text_input("关键词搜索（匹配法规名、条款号、摘要内容）", "")
        categories = []
        for item in REGULATIONS.values():
            if item["category"] not in categories:
                categories.append(item["category"])

        matched_total = 0
        for cat in categories:
            st.markdown(f"### {cat}")
            cat_matched = 0
            for aid, item in REGULATIONS.items():
                if item["category"] != cat:
                    continue
                text = f"{item['law']}{item['article']}{item['summary']}"
                if keyword and keyword.lower() not in text.lower():
                    continue
                cat_matched += 1
                with st.expander(f"{item['law']}{item['article']}"):
                    st.markdown(item["summary"])
            if cat_matched == 0:
                st.caption("（无匹配结果）")
            matched_total += cat_matched
        if keyword:
            st.caption(f"关键词「{keyword}」共匹配 {matched_total} 条法条。")

    with tab_case:
        st.caption("以下案例均来自公开报道，金额与细节以官方通报为准。")
        for case in CASES:
            with st.expander(f"{case['name']}（{case['time']}）—— {case['fine']}"):
                st.markdown(f"- **处罚机构**：{case['authority']}")
                st.markdown(f"- **事由**：{case['reason']}")
                st.markdown(f"- **关联维度**：{'、'.join(case['dimensions'])}")
                st.markdown(f"- **启示**：{case['lesson']}")


# ---------------- 主入口：侧边栏导航 ----------------
def main():
    # 初始化会话状态
    defaults = {
        "answers": default_answers(),
        "hits": None,
        "explanations": {},
        "roadmap_done": set(),
        "doc_result": None,
        "doc_text": "",
        "policy_text": None,
        "policy_check": None,
        "just_evaluated": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    st.sidebar.title("🛡️ 数盾 DataShield")
    page = st.sidebar.radio(
        "页面导航",
        ["首页", "文档智能分析", "合规自查问卷", "合规仪表盘", "整改路线图",
         "合规报告", "隐私政策生成", "隐私政策体检", "历史趋势", "法条与案例"],
    )
    st.sidebar.divider()
    if is_llm_available():
        st.sidebar.caption("🤖 AI 功能：已启用")
    else:
        st.sidebar.caption("📋 AI 功能：未配置（纯规则模式）")
    st.sidebar.caption("结果仅供参考，不构成法律意见")

    pages = {
        "首页": page_home,
        "文档智能分析": page_doc_analysis,
        "合规自查问卷": page_questionnaire,
        "合规仪表盘": page_dashboard,
        "整改路线图": page_roadmap,
        "合规报告": page_report,
        "隐私政策生成": page_policy_generator,
        "隐私政策体检": page_policy_checker,
        "历史趋势": page_history,
        "法条与案例": page_laws_cases,
    }
    pages[page]()


if __name__ == "__main__":
    main()
