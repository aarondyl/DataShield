# -*- coding: utf-8 -*-
"""问卷定义模块：六大模块、动态追问。

app.py 按本文件的结构渲染表单；doc_analyzer 用它生成给 LLM 的题目清单；
presets.py 的行业预设答案也以这里的 key 为准。

字段说明：
    key       答案 dict 中的键
    module    所属模块名（页面分节展示）
    text      题干
    type      控件类型：yesno（是/否）/ select（单选）/ multiselect（多选）
    options   select / multiselect 的可选项
    show_if   函数(answers)->bool，返回 False 时该题隐藏（动态追问），答案记为默认值
    default   未展示时的默认答案
"""

from rules import (
    CROSS_BORDER_OPTIONS,
    DATA_TYPE_OPTIONS,
    DAU_OPTIONS,
    INDUSTRY_OPTIONS,
    SENSITIVE_TYPE_OPTIONS,
    STORAGE_OPTIONS,
)

QUESTION_MODULES = ["数据收集", "存储与安全", "共享与第三方", "用户权利", "告知与政策", "规模与主体"]

QUESTIONS = [
    # ========== 模块一：数据收集 ==========
    {"key": "collect_personal", "module": "数据收集", "type": "yesno",
     "text": "是否收集用户个人信息？（姓名/手机号/邮箱等）", "default": True},
    {"key": "data_types", "module": "数据收集", "type": "multiselect",
     "text": "收集哪些类型的信息？（可多选）", "options": DATA_TYPE_OPTIONS,
     "show_if": lambda a: a["collect_personal"], "default": []},
    {"key": "collect_sensitive", "module": "数据收集", "type": "yesno",
     "text": "是否收集敏感个人信息？（健康数据、生物识别、精确位置、金融账户）", "default": False},
    {"key": "sensitive_types", "module": "数据收集", "type": "multiselect",
     "text": "收集哪些敏感信息？（可多选）", "options": SENSITIVE_TYPE_OPTIONS,
     "show_if": lambda a: a["collect_sensitive"], "default": []},
    {"key": "sensitive_consent", "module": "数据收集", "type": "yesno",
     "text": "是否为敏感信息设置了「单独同意」弹窗？（不能混在整包协议里）",
     "show_if": lambda a: a["collect_sensitive"], "default": None},
    {"key": "minors_under_14", "module": "数据收集", "type": "yesno",
     "text": "是否涉及未成年人（14岁以下）数据？", "default": False},
    {"key": "guardian_consent", "module": "数据收集", "type": "yesno",
     "text": "是否有监护人同意机制？（如监护人验证、短信/邮件确认）",
     "show_if": lambda a: a["minors_under_14"], "default": None},

    # ========== 模块二：存储与安全 ==========
    {"key": "storage_location", "module": "存储与安全", "type": "select",
     "text": "数据存储在哪里？", "options": STORAGE_OPTIONS, "default": "中国境内"},
    {"key": "cross_border_measure", "module": "存储与安全", "type": "select",
     "text": "出境数据采取了哪种合规措施？", "options": CROSS_BORDER_OPTIONS,
     "show_if": lambda a: a["storage_location"] == "跨境传输到中国境外", "default": None},
    {"key": "encrypt_storage", "module": "存储与安全", "type": "yesno",
     "text": "是否对数据加密存储和传输？（如 HTTPS、字段加密）", "default": False},
    {"key": "access_control", "module": "存储与安全", "type": "yesno",
     "text": "是否建立访问权限控制？（最小授权、操作审计）", "default": False},
    {"key": "breach_plan", "module": "存储与安全", "type": "yesno",
     "text": "是否制定数据泄露应急预案？", "default": False},
    {"key": "retention_defined", "module": "存储与安全", "type": "yesno",
     "text": "是否明确各类数据的保存期限？（到期删除/匿名化）", "default": False},

    # ========== 模块三：共享与第三方 ==========
    {"key": "share_third_party", "module": "共享与第三方", "type": "yesno",
     "text": "是否向第三方共享用户数据？（如广告 SDK、数据分析服务）", "default": False},
    {"key": "sdk_disclosed", "module": "共享与第三方", "type": "yesno",
     "text": "是否在隐私政策中公示第三方 SDK/服务清单？",
     "show_if": lambda a: a["share_third_party"], "default": None},
    {"key": "third_party_agreement", "module": "共享与第三方", "type": "yesno",
     "text": "是否与第三方签署数据处理协议？",
     "show_if": lambda a: a["share_third_party"], "default": None},

    # ========== 模块四：用户权利 ==========
    {"key": "right_access", "module": "用户权利", "type": "yesno",
     "text": "是否提供查阅、复制个人信息的渠道？", "default": False},
    {"key": "right_delete", "module": "用户权利", "type": "yesno",
     "text": "是否提供删除个人信息、注销账号的渠道？", "default": False},
    {"key": "right_withdraw", "module": "用户权利", "type": "yesno",
     "text": "是否提供撤回同意的渠道？（如一键关闭授权）", "default": False},

    # ========== 模块五：告知与政策 ==========
    {"key": "privacy_policy", "module": "告知与政策", "type": "yesno",
     "text": "是否已制定并公开隐私政策？", "default": False},
    {"key": "policy_updated", "module": "告知与政策", "type": "yesno",
     "text": "隐私政策近一年内是否更新过？",
     "show_if": lambda a: a["privacy_policy"], "default": None},
    {"key": "consent_popup", "module": "告知与政策", "type": "yesno",
     "text": "首次运行时是否有隐私告知弹窗？（用户同意后才收集）", "default": False},

    # ========== 模块六：规模与主体 ==========
    {"key": "dau_scale", "module": "规模与主体", "type": "select",
     "text": "日活用户量级？", "options": DAU_OPTIONS, "default": "<1万"},
    {"key": "industry", "module": "规模与主体", "type": "select",
     "text": "所属行业？", "options": INDUSTRY_OPTIONS, "default": "通用"},
    {"key": "eu_users", "module": "规模与主体", "type": "yesno",
     "text": "是否面向欧盟用户提供服务？（决定 GDPR 是否直接适用）", "default": False},
]


def default_answers():
    """生成一份默认答案（所有问题取 default 值）。"""
    return {q["key"]: q.get("default") for q in QUESTIONS}


def normalize_answers(raw):
    """把部分填写的答案补全为完整答案：未展示的追问题目取默认值。

    doc_analyzer 预填、presets 加载后都要经过本函数，保证规则引擎拿到的字段齐全。
    """
    # 先用默认值补全缺失字段，show_if 判断才不会因缺键报错
    answers = default_answers()
    answers.update(raw)
    changed = True
    # 多轮归一：追问题目的 show_if 可能依赖其他追问题目的值
    while changed:
        changed = False
        for q in QUESTIONS:
            visible = q.get("show_if", lambda a: True)(answers)
            if not visible and answers.get(q["key"]) != q.get("default"):
                answers[q["key"]] = q.get("default")
                changed = True
    return answers


def question_index():
    """返回 {key: 题目定义} 的索引，便于按 key 查题干。"""
    return {q["key"]: q for q in QUESTIONS}
