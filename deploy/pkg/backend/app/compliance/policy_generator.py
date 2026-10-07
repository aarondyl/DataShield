# -*- coding: utf-8 -*-
"""隐私政策生成器。

根据问卷答案，用结构化模板生成隐私政策初稿（Markdown），可下载后
替换占位符（公司名、联系方式等）投入使用。配置 LLM 时可在生成器页面
对初稿做润色（见 app.py 的调用），无 LLM 时模板版也完全可用。
"""

from datetime import datetime

# 数据类型 -> 用途说明（模板措辞）
DATA_TYPE_PURPOSE = {
    "姓名/身份信息": "用于账号注册、实名认证及履行法定义务",
    "手机号/邮箱": "用于账号登录、找回密码、接收服务通知",
    "设备标识符": "用于保障账号与设备安全、统计服务运行情况",
    "日志/行为数据": "用于分析产品使用情况、改进服务质量",
    "通讯录/相册": "用于您主动使用相关功能时的内容读取（仅经授权后访问）",
    "其他": "用于实现您使用的具体功能",
}

SENSITIVE_TYPE_PURPOSE = {
    "健康数据": "用于提供健康相关核心功能，我们将采取严格保护措施",
    "生物识别": "用于身份验证等核心功能，仅在您单独同意后处理",
    "精确位置": "用于提供基于位置的服务，仅在您单独同意后收集",
    "金融账户": "用于完成支付结算，仅在您单独同意后处理",
    "其他敏感信息": "用于实现特定功能，仅在您单独同意后处理",
}


def generate_policy(answers, app_name="【产品名称】", company="【公司名称】", contact="【联系邮箱】"):
    """按问卷答案生成隐私政策初稿（Markdown 字符串）。

    参数：
        answers: 问卷答案 dict。
        app_name / company / contact: 页面上可填写的占位信息。
    """
    now = datetime.now().strftime("%Y 年 %m 月 %d 日")
    lines = [
        f"# {app_name} 隐私政策",
        "",
        f"更新日期：{now}",
        "",
        f"{app_name}（以下简称「我们」，运营主体：{company}）深知个人信息对您的重要性，"
        "我们将按照《中华人民共和国个人信息保护法》《中华人民共和国数据安全法》"
        "等法律法规要求，采取相应措施保护您的个人信息安全。",
        "",
        "请您在使用我们的产品/服务前，仔细阅读并理解本政策全部内容。",
        "",
        "## 一、我们收集和使用的个人信息",
        "",
    ]

    # ---- 收集清单 ----
    if answers.get("collect_personal"):
        lines.append("为了向您提供产品/服务，我们会收集以下信息：")
        lines.append("")
        for dt in answers.get("data_types") or []:
            purpose = DATA_TYPE_PURPOSE.get(dt, DATA_TYPE_PURPOSE["其他"])
            lines.append(f"- **{dt}**：{purpose}。")
        if not (answers.get("data_types")):
            lines.append("- 为实现功能所必需的基本个人信息。")
    else:
        lines.append("我们不主动收集您的姓名、手机号等直接身份信息。但请注意，"
                     "产品运行所需的设备信息与日志可能依法构成个人信息，我们同样按本政策保护。")
    lines.append("")

    # ---- 敏感信息 ----
    if answers.get("collect_sensitive"):
        lines += [
            "## 二、敏感个人信息的处理",
            "",
            "我们可能处理以下**敏感个人信息**，处理前将**单独征得您的同意**：",
            "",
        ]
        for st_ in answers.get("sensitive_types") or []:
            purpose = SENSITIVE_TYPE_PURPOSE.get(st_, SENSITIVE_TYPE_PURPOSE["其他敏感信息"])
            lines.append(f"- **{st_}**：{purpose}。")
        lines += [
            "",
            "您可以随时通过本政策第九条的联系方式撤回上述单独同意。",
            "",
        ]

    # ---- 未成年人 ----
    if answers.get("minors_under_14"):
        lines += [
            "## 三、未成年人个人信息保护",
            "",
            "我们的产品/服务可能涉及不满十四周岁未成年人的个人信息。处理此类信息前，"
            "我们将取得其父母或其他监护人的同意，并制定专门的未成年人个人信息处理规则。",
            "监护人如对未成年人个人信息有疑问，可通过本政策第九条的方式联系我们。",
            "",
        ]

    # ---- 第三方共享 ----
    lines.append("## 四、第三方共享与 SDK")
    lines.append("")
    if answers.get("share_third_party"):
        lines += [
            "为实现特定功能，我们可能接入第三方 SDK 或向第三方提供必要的个人信息。"
            "我们将：",
            "",
            "1. 在本政策附件/清单中公示第三方 SDK 及服务的名称、收集的信息类型与用途；",
            "2. 与第三方签署数据处理协议，要求其在约定范围内处理并采取安全保护措施；",
            "3. 向第三方提供个人信息前，依法取得您的单独同意。",
        ]
        for sdk in answers.get("third_party_sdks") or []:
            lines.append(f"- **{sdk}**：【待核对】请补充该 SDK 的提供方、收集信息、使用目的和隐私政策链接。")
    else:
        lines.append("我们目前不向第三方共享您的个人信息。如未来接入第三方服务，"
                     "我们将提前在本政策中公示并依法取得您的同意。")
    lines.append("")

    # ---- 存储与跨境 ----
    lines += ["## 五、信息的存储", ""]
    loc = answers.get("storage_location", "中国境内")
    if loc == "跨境传输到中国境外":
        lines += [
            "我们在中华人民共和国境内收集和产生的个人信息，可能因业务需要传输至中国境外处理。"
            "我们将依法通过安全评估、订立标准合同或保护认证等路径开展数据出境活动，"
            "并采取必要措施保障境外接收方的保护水平不低于法定要求。",
        ]
    elif loc == "欧盟境内":
        lines.append("您的个人信息存储于欧盟境内的服务器，我们按照 GDPR 的要求开展处理活动。")
    else:
        lines.append("我们在中华人民共和国境内收集和产生的个人信息存储于中国境内。")
    if answers.get("retention_defined"):
        lines.append("我们仅在实现处理目的所必需的最短期限内保存您的个人信息，到期后删除或匿名化。")
    else:
        lines.append("【待补充】请明确各类信息的保存期限，到期后删除或匿名化。")
    lines.append("")

    # ---- 安全措施 ----
    lines += ["## 六、信息的安全保护", ""]
    measures = []
    if answers.get("encrypt_storage"):
        measures.append("对个人信息采取加密存储与加密传输（HTTPS/TLS）")
    if answers.get("access_control"):
        measures.append("建立最小授权的访问权限控制与操作审计机制")
    if answers.get("breach_plan"):
        measures.append("制定数据安全事件应急预案，发生泄露时及时处置并依法通知")
    if measures:
        lines.append("我们已采取以下措施保护您的个人信息：")
        lines += [f"- {m}；" for m in measures]
    else:
        lines.append("【待补充】请说明你们采取的安全保护措施（如加密、权限控制、应急预案等）。")
    lines.append("")

    # ---- 用户权利 ----
    lines += ["## 七、您的权利", ""]
    rights = []
    if answers.get("right_access"):
        rights.append("**查阅、复制权**：您可以在产品内查阅、复制您的个人信息")
    if answers.get("right_delete"):
        rights.append("**删除权**：您可以删除个人信息或注销账号，我们将及时删除或匿名化")
    if answers.get("right_withdraw"):
        rights.append("**撤回同意权**：您可以随时撤回已作出的授权同意")
    if rights:
        lines += [f"- {r}；" for r in rights]
    else:
        lines.append("【待补充】请提供查阅、复制、删除、撤回同意、注销账号的具体渠道。")
    lines.append("我们将在法律法规规定的期限内响应您的请求。")
    lines.append("")

    # ---- 政策更新与联系方式 ----
    lines += [
        "## 八、本政策的更新",
        "",
        "本政策可能随业务调整而更新。重大变更时，我们将以弹窗、站内通知等显著方式"
        "提示您，并在必要时重新取得您的同意。",
        "",
        "## 九、联系我们",
        "",
        f"如对本政策或个人信息保护有任何疑问，可通过以下方式联系我们：{contact}。",
        "",
        "---",
        "",
        "*本初稿由 数盾 DataShield 根据自查问卷自动生成，使用前请替换所有【占位符】，"
        "并请结合实际业务核对，必要时咨询专业律师。*",
    ]
    return "\n".join(lines)
