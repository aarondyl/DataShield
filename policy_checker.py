# -*- coding: utf-8 -*-
"""隐私政策文本体检模块。

粘贴现有隐私政策全文，检查法定必备要素是否覆盖：
    规则模式：按关键词组匹配（离线可用，确定性结果）；
    AI 模式：由 app.py 调用 llm_explainer 做语义级复核（可选增强）。
"""

# 12 项必备要素：名称、说明、关键词组（组内任一词命中即视为覆盖该要素）
REQUIRED_ELEMENTS = [
    {"key": "controller", "name": "处理者身份与联系方式",
     "hint": "写明运营主体名称、注册地址、联系方式（个保法第17条、GDPR第13条）",
     "keywords": ["联系我们", "联系方式", "公司名称", "运营者", "主体", "邮箱", "controller", "contact"]},
    {"key": "purpose", "name": "处理目的与方式",
     "hint": "逐项说明收集信息的目的、方式（个保法第17条、GDPR第13条）",
     "keywords": ["目的", "用途", "用于", "为了", "purpose"]},
    {"key": "data_list", "name": "收集的个人信息种类清单",
     "hint": "列明收集的信息种类（个保法第17条）",
     "keywords": ["收集", "信息种类", "个人信息包括", "我们会收集", "collect"]},
    {"key": "retention", "name": "保存期限",
     "hint": "说明保存期限或期限确定方法（个保法第19条、GDPR第13条）",
     "keywords": ["保存期限", "保留", "存储期限", "最短时间", "retention", "期限"]},
    {"key": "sensitive", "name": "敏感个人信息单独说明",
     "hint": "单独列出敏感信息种类并取得单独同意（个保法第29条、GDPR第9条）",
     "keywords": ["敏感个人信息", "敏感信息", "单独同意", "生物识别", "sensitive"]},
    {"key": "third_party", "name": "第三方共享与 SDK 清单",
     "hint": "公示第三方/SDK 名称、收集信息、用途（个保法第23条）",
     "keywords": ["第三方", "SDK", "sdk", "共享", "合作伙伴", "third party"]},
    {"key": "minors", "name": "未成年人保护条款",
     "hint": "14岁以下未成年人须监护人同意与专门规则（个保法第31条、GDPR第8条）",
     "keywords": ["未成年人", "儿童", "监护人", "十四周岁", "14周岁", "children"]},
    {"key": "rights", "name": "用户权利及行使方式",
     "hint": "说明查阅、复制、更正、删除、撤回同意等权利及渠道（个保法第44条、GDPR第12-14条）",
     "keywords": ["查阅", "复制", "更正", "您的权利", "访问您的", "your rights"]},
    {"key": "delete_account", "name": "删除与账号注销渠道",
     "hint": "提供删除个人信息、注销账号的方法（个保法第47条、GDPR第17条）",
     "keywords": ["注销", "删除您的", "删除个人", "删除账号", "delete"]},
    {"key": "withdraw", "name": "撤回同意方式",
     "hint": "提供便捷的撤回同意途径（个保法第15条、GDPR第7条）",
     "keywords": ["撤回同意", "撤回授权", "取消授权", "withdraw"]},
    {"key": "cross_border", "name": "跨境传输说明",
     "hint": "涉及出境时说明接收方、目的与保障措施（个保法第38条、GDPR第44-49条）；不出境也应明确声明",
     "keywords": ["跨境", "境外", "出境", "海外", "cross-border", "transfer"]},
    {"key": "update", "name": "政策更新机制",
     "hint": "说明政策更新时的通知方式（个保法第17条）",
     "keywords": ["本政策的更新", "政策更新", "修订", "变更", "updated", "更新日期"]},
]


def check_policy(text):
    """检查隐私政策文本的要素覆盖情况。

    参数：text: str，隐私政策全文。
    返回：dict：
        {
          "total": 要素总数,
          "covered": 已覆盖数,
          "coverage": 覆盖率(0-100),
          "items": [{"name","hint","covered","matched"}...]，matched 为命中的关键词
        }
    """
    text_l = (text or "").lower()
    items = []
    for el in REQUIRED_ELEMENTS:
        matched = [kw for kw in el["keywords"] if kw.lower() in text_l]
        items.append({
            "name": el["name"],
            "hint": el["hint"],
            "covered": bool(matched),
            "matched": matched,
        })
    covered = sum(1 for i in items if i["covered"])
    total = len(items)
    return {
        "total": total,
        "covered": covered,
        "coverage": round(covered / total * 100),
        "items": items,
    }
