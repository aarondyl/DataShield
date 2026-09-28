# -*- coding: utf-8 -*-
"""LLM 解释生成模块（可选，带降级）。

配置来源（优先级：环境变量 > Streamlit secrets > config.py > 内置默认值）：
    API Key   DEEPSEEK_API_KEY   / st.secrets["DEEPSEEK_API_KEY"] / config.py 的 API_KEY
    base_url  DEEPSEEK_BASE_URL  / st.secrets / config.py 的 BASE_URL / 默认 https://api.deepseek.com/v1
    model     DEEPSEEK_MODEL     / st.secrets / config.py 的 MODEL    / 默认 deepseek-v4.1-flash

若未配置 API Key，或调用过程中出现任何异常（无网络、超时、鉴权失败等），
自动降级为"纯规则模式"：用内置模板/算法给出结果，保证应用离线也能完整运行。
"""

import json
import os
import re

from regulations_data import REGULATIONS

# 内置默认值（config.py、secrets、环境变量都未设置时使用）
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4.1-flash"
REQUEST_TIMEOUT = 20  # 秒，超时后降级为模板解释


def _load_config_file():
    """读取 config.py 中的配置（可选）。文件不存在、缺字段或出错时返回空 dict。"""
    try:
        import config
        return {
            key: getattr(config, key)
            for key in ("API_KEY", "BASE_URL", "MODEL", "TIMEOUT", "TEMPERATURE", "MAX_TOKENS")
            if getattr(config, key, None) not in (None, "")
        }
    except Exception:
        return {}


def _load_streamlit_secrets():
    """读取 Streamlit secrets（部署到 Streamlit Cloud 时使用）。本地未配置时返回空 dict。"""
    try:
        import streamlit as st
        out = {}
        if "DEEPSEEK_API_KEY" in st.secrets:
            out["API_KEY"] = st.secrets["DEEPSEEK_API_KEY"]
        if "DEEPSEEK_BASE_URL" in st.secrets:
            out["BASE_URL"] = st.secrets["DEEPSEEK_BASE_URL"]
        if "DEEPSEEK_MODEL" in st.secrets:
            out["MODEL"] = st.secrets["DEEPSEEK_MODEL"]
        return out
    except Exception:
        return {}


def get_settings():
    """汇总 LLM 配置：环境变量 > Streamlit secrets > config.py > 内置默认值。"""
    cfg = {**_load_config_file(), **_load_streamlit_secrets()}
    # 注意上面合并顺序：secrets 覆盖 config.py；下面环境变量再覆盖两者
    return {
        "api_key": os.environ.get("DEEPSEEK_API_KEY") or cfg.get("API_KEY", ""),
        "base_url": os.environ.get("DEEPSEEK_BASE_URL") or cfg.get("BASE_URL", DEFAULT_BASE_URL),
        "model": os.environ.get("DEEPSEEK_MODEL") or cfg.get("MODEL", DEFAULT_MODEL),
        "timeout": cfg.get("TIMEOUT", REQUEST_TIMEOUT),
        "temperature": cfg.get("TEMPERATURE", 0.3),
        "max_tokens": cfg.get("MAX_TOKENS", 600),
    }


def is_llm_available():
    """判断是否已配置 API Key（不实际发起请求）。"""
    return bool(get_settings()["api_key"])


def _chat(system_prompt, user_prompt, max_tokens=None):
    """统一的 LLM 调用入口。返回文本；失败抛出异常，由调用方降级。"""
    settings = get_settings()
    if not settings["api_key"]:
        raise RuntimeError("未配置 API Key")
    # 延迟导入：未安装 openai 包时不影响纯规则模式运行
    from openai import OpenAI

    client = OpenAI(
        api_key=settings["api_key"],
        base_url=settings["base_url"],
        timeout=settings["timeout"],
    )
    resp = client.chat.completions.create(
        model=settings["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings["temperature"],
        max_tokens=max_tokens or settings["max_tokens"],
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise ValueError("LLM 返回了空内容")
    return text


def _build_prompt(rule, article_text):
    """构造发给 LLM 的提示词：要求生成通俗解释（100字以内）+ 整改操作步骤。"""
    return (
        "你是一名数据合规顾问，服务对象是没有法律背景的中小 App 开发者。\n"
        "请针对下面这条命中的合规风险，输出两部分内容：\n"
        "1.【通俗解释】用不超过 100 字说明这个风险为什么违法、可能带来什么后果；\n"
        "2.【整改步骤】给出 3-5 条具体可执行的整改操作步骤，每条一行，以序号开头。\n"
        "要求：全部使用中文，语言通俗，不要引用法条原文，不要输出其他内容。\n\n"
        f"命中规则：{rule['rule_id']}\n"
        f"命中条件：{rule['condition']}\n"
        f"风险等级：{rule['level']}\n"
        f"风险描述：{rule['risk']}\n"
        f"初步整改建议：{rule['advice']}\n"
        f"涉及法条：\n{article_text}\n"
    )


def _fallback_explanation(rule):
    """内置模板解释（降级模式）。离线或未配置 Key 时使用。"""
    return (
        f"【通俗解释】{rule['risk']}命中规则 {rule['rule_id']}（{rule['condition']}），"
        f"属于{rule['level']}风险事项，建议优先处理。\n"
        f"【整改步骤】\n"
        f"1. 阅读风险描述，确认业务中对应环节的实际处理行为；\n"
        f"2. 对照整改建议：{rule['advice']}\n"
        f"3. 逐项落实后重新运行本工具自查；\n"
        f"4. 涉及重大数据处理决策时，建议咨询专业律师。"
    )


def _articles_to_text(article_ids):
    """把法条编号列表整理成给 LLM 参考的文本。"""
    lines = []
    for aid in article_ids:
        item = REGULATIONS.get(aid)
        if item:
            lines.append(f"- {item['law']}{item['article']}：{item['summary']}")
    return "\n".join(lines) if lines else "（无）"


def explain_risk(rule, article_text=None):
    """为一条命中规则生成解释（通俗解释 + 整改步骤）。

    参数：
        rule: dict，rules.evaluate_rules 返回的单条命中记录。
        article_text: str 或 None，法条摘要文本；为 None 时自动按 rule['articles'] 生成。

    返回：
        dict：{"text": 解释文本, "source": "llm" 或 "fallback"}
        任何调用失败都会降级为内置模板，绝不抛异常。
    """
    if article_text is None:
        article_text = _articles_to_text(rule.get("articles", []))

    try:
        text = _chat(
            "你是一名面向开发者的数据合规顾问，回答简洁通俗。",
            _build_prompt(rule, article_text),
        )
        return {"text": text, "source": "llm"}
    except Exception:
        # 未配置 Key、网络错误、鉴权失败、超时、返回格式异常等：一律降级为模板解释
        return {"text": _fallback_explanation(rule), "source": "fallback"}


def _extract_json(text):
    """从 LLM 回复中提取 JSON 对象（容忍 ```json 代码块和前后杂文本）。"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("回复中未找到 JSON")
    return json.loads(m.group(0))


def analyze_document(text, questions_brief):
    """让 LLM 阅读项目文档，代为回答问卷（返回答案 dict）。

    参数：
        text: 文档正文（已截断到合理长度）。
        questions_brief: 题目简述列表 [{key, text, type, options}]，由 doc_analyzer 生成。

    返回：dict，{题目 key: 答案}；失败返回 None（调用方改用关键词启发式）。
    """
    q_lines = []
    for q in questions_brief:
        if q["type"] == "yesno":
            q_lines.append(f"- {q['key']}（布尔 true/false）：{q['text']}")
        elif q["type"] == "select":
            q_lines.append(f"- {q['key']}（单选，从 {q['options']} 中选一个）：{q['text']}")
        else:
            q_lines.append(f"- {q['key']}（多选数组，元素从 {q['options']} 中选）：{q['text']}")
    prompt = (
        "下面是一份 App/网站的项目文档，以及一份数据合规问卷。\n"
        "请你基于文档内容，以 JSON 对象的形式代为填写问卷：键为题号，值为答案。\n"
        "只输出 JSON，不要输出任何其他文字。文档未提及的，布尔题填 false，"
        "单选题填最保守的选项，多选题填空数组。\n\n"
        f"【问卷】\n{chr(10).join(q_lines)}\n\n"
        f"【项目文档】\n{text}\n"
    )
    try:
        raw = _chat(
            "你是一名严谨的数据合规分析师，只输出合法 JSON。",
            prompt,
            max_tokens=1200,
        )
        data = _extract_json(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def review_policy_text(text):
    """让 LLM 对隐私政策文本做语义级复核。失败返回 None（调用方用关键词结果即可）。"""
    prompt = (
        "你是一名数据合规律师。下面是一份隐私政策全文，请用中文给出复核意见，"
        "包括：1. 总体评价（不超过 80 字）；2. 3-6 条具体修改建议（每条一行，以序号开头）。"
        "语言通俗，面向非法律背景的开发者。\n\n"
        f"【隐私政策全文】\n{text}\n"
    )
    try:
        return _chat("你是一名严谨的数据合规律师。", prompt, max_tokens=800)
    except Exception:
        return None


def polish_policy(policy_text):
    """让 LLM 润色生成的隐私政策初稿。失败返回 None（调用方使用模板版即可）。"""
    prompt = (
        "你是一名数据合规律师。请在不改变事实内容的前提下，润色下面这份隐私政策初稿，"
        "使其表述更规范、完整、专业；保留所有【占位符】和 Markdown 结构，直接输出润色后全文。\n\n"
        f"{policy_text}\n"
    )
    try:
        return _chat("你是一名严谨的数据合规律师。", prompt, max_tokens=3000)
    except Exception:
        return None
