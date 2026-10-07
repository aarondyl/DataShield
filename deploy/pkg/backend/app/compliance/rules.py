# -*- coding: utf-8 -*-
"""合规规则引擎（核心模块）。

工作模式：问卷答案 -> 触发规则 -> 输出风险。
规则用纯 Python if-else 实现，不引入复杂规则引擎。

每条命中输出：规则ID、所属维度、命中条件、风险等级（高/中/低）、
违反的法条、一句话风险描述、整改建议。

问卷答案字段（由 app.py 按 questionnaire.py 的定义收集）：
    collect_personal      是否收集用户个人信息（bool）
    data_types            收集的信息类型（list[str]）
    collect_sensitive     是否收集敏感个人信息（bool）
    sensitive_types       敏感信息类型（list[str]）
    sensitive_consent     敏感信息是否有单独同意弹窗（bool/None）
    minors_under_14       是否涉及 14 岁以下未成年人数据（bool）
    guardian_consent      是否有监护人同意机制（bool/None）
    storage_location      数据存储位置（STORAGE_OPTIONS 之一）
    cross_border_measure  出境合规措施（CROSS_BORDER_OPTIONS 之一/None）
    encrypt_storage       是否加密存储和传输（bool）
    access_control        是否有访问权限控制（bool）
    breach_plan           是否有数据泄露应急预案（bool）
    retention_defined     是否明确数据保存期限（bool）
    share_third_party     是否向第三方共享（bool）
    sdk_disclosed         第三方 SDK 清单是否公示（bool/None）
    third_party_agreement 是否与第三方签数据处理协议（bool/None）
    right_access          是否提供查阅、复制渠道（bool）
    right_delete          是否提供删除、注销渠道（bool）
    right_withdraw        是否提供撤回同意渠道（bool）
    privacy_policy        是否已制定并公开隐私政策（bool）
    policy_updated        隐私政策近一年是否更新（bool/None）
    consent_popup         首次运行是否有告知弹窗（bool）
    dau_scale             日活用户量级（DAU_OPTIONS 之一）
    industry              所属行业（INDUSTRY_OPTIONS 之一）
    eu_users              是否面向欧盟用户（bool）
"""

from app.compliance.regulations_data import REGULATIONS

# 风险等级排序权重（数值越小越严重，用于结果排序）
LEVEL_ORDER = {"高": 0, "中": 1, "低": 2}

# 风险等级对应 emoji，用于页面配色区分（红/黄/绿）
LEVEL_EMOJI = {"高": "🔴", "中": "🟡", "低": "🟢"}

# 各风险等级扣分（总分与维度分共用：起始 100 分，下限 0 分）
LEVEL_DEDUCT = {"高": 15, "中": 8, "低": 3}

# 问卷可选项（app.py 表单、规则、文档分析共用，避免硬编码不一致）
STORAGE_OPTIONS = ["中国境内", "欧盟境内", "跨境传输到中国境外"]
CROSS_BORDER_OPTIONS = ["无合规措施", "标准合同", "安全评估", "保护认证", "不确定"]
DAU_OPTIONS = ["<1万", "1-10万", "10万+", "100万+"]
INDUSTRY_OPTIONS = ["通用", "电商", "社交", "教育", "医疗健康", "金融"]
DATA_TYPE_OPTIONS = ["姓名/身份信息", "手机号/邮箱", "设备标识符", "日志/行为数据", "通讯录/相册", "其他"]
SENSITIVE_TYPE_OPTIONS = ["健康数据", "生物识别", "精确位置", "金融账户", "其他敏感信息"]

# 七大合规评估维度（仪表盘雷达图按此展示）
DIMENSIONS = [
    "告知与同意",
    "数据安全",
    "用户权利",
    "跨境传输",
    "第三方管理",
    "未成年人保护",
    "综合管理",
]


def _hit(rule_id, dimension, condition, level, articles, risk, advice):
    """构造一条命中记录（内部辅助函数）。"""
    return {
        "rule_id": rule_id,
        "dimension": dimension,
        "condition": condition,
        "level": level,
        "articles": articles,
        "risk": risk,
        "advice": advice,
    }


def evaluate_rules(a):
    """运行规则引擎。

    参数：
        a: dict，问卷答案，字段见模块 docstring。

    返回：
        list[dict]，所有命中的风险记录，按风险等级（高->中->低）、维度排序。
        若没有任何风险项命中，则返回仅含 R8「全部合规」低风险提示的列表。
    """
    hits = []

    # ================= 维度一：告知与同意 =================

    # R101：收集个人信息但未提供隐私政策 -> 高
    if a["collect_personal"] and not a["privacy_policy"]:
        hits.append(_hit(
            "R101", "告知与同意",
            "收集个人信息，但尚未制定并公开隐私政策",
            "高",
            ["PIPL-17", "GDPR-12-14"],
            "收集个人信息却未公开隐私政策，属于未履行告知义务，是监管处罚中最常见的情形。",
            "立即制定并公开隐私政策，写明收集的信息种类、使用目的、保存期限和用户权利渠道，并在 App/网站显著位置提供入口。",
        ))

    # R102：有隐私政策但首次运行无告知弹窗 -> 中
    if a["collect_personal"] and a["privacy_policy"] and not a["consent_popup"]:
        hits.append(_hit(
            "R102", "告知与同意",
            "已公开隐私政策，但首次运行时无告知弹窗",
            "中",
            ["PIPL-17", "GDPR-12-14"],
            "仅在页面角落放置隐私政策链接，未在首次运行时以弹窗等显著方式告知，可能被认定为告知不充分。",
            "在 App 首次启动时增加隐私政策弹窗（展示收集要点并提供全文链接），用户点击同意后再开始收集。",
        ))

    # R103：收集敏感个人信息且无隐私政策 -> 高
    if a["collect_sensitive"] and not a["privacy_policy"]:
        hits.append(_hit(
            "R103", "告知与同意",
            "收集敏感个人信息，但未取得任何形式的告知同意",
            "高",
            ["PIPL-29", "GDPR-9"],
            "健康、生物识别、精确位置、金融账户等敏感信息必须取得单独同意，未取得的处理行为直接违法。",
            "立即暂停相关收集，补齐隐私政策并对敏感信息单独取得同意后再恢复。",
        ))

    # R104：收集敏感个人信息，有隐私政策但无单独同意弹窗 -> 高
    if a["collect_sensitive"] and a["privacy_policy"] and a.get("sensitive_consent") is False:
        hits.append(_hit(
            "R104", "告知与同意",
            "收集敏感个人信息，但未设置单独同意弹窗",
            "高",
            ["PIPL-29", "GDPR-9"],
            "把敏感信息授权混在整包隐私政策里一并勾选，不构成《个保法》要求的「单独同意」。",
            "对敏感个人信息单独弹窗或单独页面取得同意，说明处理必要性和对个人权益的影响，并支持单独撤回。",
        ))

    # R105：敏感信息单独同意已落实 -> 低（提醒留存记录）
    if a["collect_sensitive"] and a.get("sensitive_consent") is True:
        hits.append(_hit(
            "R105", "告知与同意",
            "敏感个人信息已设置单独同意",
            "低",
            ["PIPL-29"],
            "单独同意机制已具备，需保留同意记录以备举证。",
            "留存每次单独同意的时间、版本、操作日志，隐私政策更新后重新取得同意。",
        ))

    # R106：隐私政策超过一年未更新 -> 中
    if a["privacy_policy"] and a.get("policy_updated") is False:
        hits.append(_hit(
            "R106", "告知与同意",
            "隐私政策超过一年未更新",
            "中",
            ["PIPL-17"],
            "隐私政策内容与当前实际收集行为可能已不一致，属于告知不真实、不准确。",
            "核对隐私政策与实际收集行为（含第三方 SDK）是否一致，更新文本并重新提示用户。",
        ))

    # R107：告知机制完善 -> 低（保持）
    if a["collect_personal"] and a["privacy_policy"] and a["consent_popup"]:
        hits.append(_hit(
            "R107", "告知与同意",
            "告知与同意机制较为完善",
            "低",
            ["PIPL-17"],
            "隐私政策与启动弹窗均已具备，告知义务履行较好。",
            "保持现有机制，业务功能变化时同步更新告知内容。",
        ))

    # R108：面向欧盟用户但隐私政策未考虑多语言 -> 低
    if a["privacy_policy"] and a["eu_users"]:
        hits.append(_hit(
            "R108", "告知与同意",
            "面向欧盟用户，隐私政策需满足 GDPR 透明度要求",
            "低",
            ["GDPR-12-14"],
            "GDPR 要求以简明、易懂语言告知，面向欧盟用户通常需要提供英文版本。",
            "提供英文版隐私政策，并确认包含控制者身份、处理依据、保存期限等 GDPR 必备要素。",
        ))

    # ================= 维度二：数据安全 =================

    # R201：收集敏感信息但未加密 -> 高
    if a["collect_sensitive"] and not a["encrypt_storage"]:
        hits.append(_hit(
            "R201", "数据安全",
            "收集敏感个人信息，但未加密存储/传输",
            "高",
            ["PIPL-51", "GDPR-32"],
            "敏感个人信息以明文存储或传输，一旦泄露将造成严重后果，且直接违反安全保护义务。",
            "对敏感字段使用强加密存储（如 AES）、全程 HTTPS/TLS 传输，密钥与数据分离管理。",
        ))

    # R202：收集个人信息但未加密 -> 中
    if a["collect_personal"] and not a["encrypt_storage"]:
        hits.append(_hit(
            "R202", "数据安全",
            "收集个人信息，但未加密存储/传输",
            "中",
            ["PIPL-51", "GDPR-32"],
            "未采取加密等基本安全技术措施，发生泄露时难以主张已尽保护义务。",
            "全站启用 HTTPS，数据库中手机号、邮箱等字段加密或脱敏存储。",
        ))

    # R203：无访问权限控制 -> 中
    if a["collect_personal"] and not a["access_control"]:
        hits.append(_hit(
            "R203", "数据安全",
            "未建立数据访问权限控制",
            "中",
            ["PIPL-51", "GDPR-32"],
            "内部人员可随意访问用户数据，属于未落实最小必要和权限管理要求。",
            "按岗位最小授权，开启数据库访问审计日志，离职及时回收权限。",
        ))

    # R204：无数据泄露应急预案 -> 中
    if a["collect_personal"] and not a["breach_plan"]:
        hits.append(_hit(
            "R204", "数据安全",
            "未制定数据泄露应急预案",
            "中",
            ["PIPL-57", "GDPR-33"],
            "发生泄露时无法及时处置和上报，GDPR 要求 72 小时内向监管机构报告。",
            "制定泄露应急预案：明确发现、止损、评估、通知用户和报告监管的流程与责任人。",
        ))

    # R205：未明确数据保存期限 -> 中
    if a["collect_personal"] and not a["retention_defined"]:
        hits.append(_hit(
            "R205", "数据安全",
            "未明确数据保存期限",
            "中",
            ["PIPL-19"],
            "保存期限未明确或未遵守「实现目的所必需的最短时间」，超期留存加大泄露面。",
            "为每类数据设定保存期限并写入隐私政策，到期自动删除或匿名化。",
        ))

    # R206：日活 10 万以上且处理敏感数据 -> 中（分类分级）
    if a["dau_scale"] in ("10万+", "100万+") and a["collect_sensitive"]:
        hits.append(_hit(
            "R206", "数据安全",
            "日活 10 万以上且处理敏感个人信息",
            "中",
            ["DSL-21"],
            "大规模处理敏感数据，可能被认定为重要数据或受到重点监管。",
            "按照《数据安全法》第 21 条建立数据分类分级保护制度，对敏感数据实施重点保护。",
        ))

    # R207：日活 100 万+ -> 中（等保与重要数据识别）
    if a["dau_scale"] == "100万+" and a["collect_personal"]:
        hits.append(_hit(
            "R207", "数据安全",
            "日活 100 万以上，处理规模巨大",
            "中",
            ["DSL-21", "PIPL-58"],
            "超大规模平台可能落入「重要互联网平台」监管范畴，义务显著加重。",
            "开展网络安全等级保护定级备案，识别重要数据，评估是否构成《个保法》第 58 条的「守门人」平台。",
        ))

    # R208：日活 1-10 万且处理敏感数据 -> 低（提前布局）
    if a["dau_scale"] == "1-10万" and a["collect_sensitive"]:
        hits.append(_hit(
            "R208", "数据安全",
            "日活 1-10 万且处理敏感个人信息",
            "低",
            ["DSL-21"],
            "规模虽未达重点监管量级，但敏感数据处理量增长快，宜提前布局。",
            "提前开展数据分类分级自查，对敏感数据先行落实加密存储和最小权限访问。",
        ))

    # R209：安全措施完善 -> 低（保持）
    if a["collect_personal"] and a["encrypt_storage"] and a["access_control"] and a["breach_plan"]:
        hits.append(_hit(
            "R209", "数据安全",
            "安全技术与管理措施较为完善",
            "低",
            ["PIPL-51"],
            "加密、权限控制、应急预案均已具备。",
            "保持现有措施，每年至少开展一次安全演练和渗透测试。",
        ))

    # ================= 维度三：用户权利 =================

    # R301：无查阅、复制渠道 -> 中
    if a["collect_personal"] and not a["right_access"]:
        hits.append(_hit(
            "R301", "用户权利",
            "未提供查阅、复制个人信息的渠道",
            "中",
            ["PIPL-44", "GDPR-12-14"],
            "用户无法查阅、复制自己的个人信息，侵犯了法定知情权和决定权。",
            "在产品内提供「个人信息副本导出」或查阅入口，并说明响应时限。",
        ))

    # R302：无删除、注销渠道 -> 中
    if a["collect_personal"] and not a["right_delete"]:
        hits.append(_hit(
            "R302", "用户权利",
            "未提供删除个人信息、注销账号的渠道",
            "中",
            ["PIPL-47", "GDPR-17"],
            "用户无法行使删除权（被遗忘权），是 App 通报下架的高发原因。",
            "提供明显的账号注销和数据删除入口，注销后及时删除或匿名化数据。",
        ))

    # R303：无撤回同意渠道 -> 中
    if a["collect_personal"] and not a["right_withdraw"]:
        hits.append(_hit(
            "R303", "用户权利",
            "未提供撤回同意的渠道",
            "中",
            ["PIPL-15", "GDPR-7"],
            "同意必须可以自由撤回，且撤回应当与作出同意同样便捷。",
            "在设置页提供一键撤回授权（含个性化推荐、敏感信息授权）的开关。",
        ))

    # R304：权利机制完善 -> 低（响应时限提醒）
    if (a["collect_personal"] and a["right_access"] and a["right_delete"] and a["right_withdraw"]):
        hits.append(_hit(
            "R304", "用户权利",
            "用户权利机制较为完善",
            "低",
            ["GDPR-12-14", "PIPL-44"],
            "三类权利渠道均已具备，需注意响应时限。",
            "建立权利请求受理台账，GDPR 要求一般不超过一个月响应，确保渠道真实可用。",
        ))

    # ================= 维度四：跨境传输 =================

    # R401：跨境传输且无任何合规措施 -> 高
    if a["storage_location"] == "跨境传输到中国境外" and a.get("cross_border_measure") in (None, "无合规措施", "不确定"):
        hits.append(_hit(
            "R401", "跨境传输",
            "数据跨境传输至境外，但未通过安全评估/标准合同/保护认证",
            "高",
            ["DSL-31", "PIPL-38", "GDPR-44-49"],
            "向境外提供个人信息须具备法定出境路径，无任何合规安排的跨境传输风险极高。",
            "尽快选择并落实出境路径（安全评估 / 标准合同备案 / 保护认证），与境外接收方签署数据处理协议。",
        ))

    # R402：跨境传输且已选择合规路径 -> 中（落实提醒）
    if a["storage_location"] == "跨境传输到中国境外" and a.get("cross_border_measure") in ("标准合同", "安全评估", "保护认证"):
        hits.append(_hit(
            "R402", "跨境传输",
            "数据跨境传输，已选择合规路径",
            "中",
            ["PIPL-38", "GDPR-44-49"],
            "出境路径已选定，仍需完成备案/申报手续并持续监督境外接收方。",
            "完成标准合同备案或评估申报，在隐私政策中披露出境情况，定期审计境外接收方。",
        ))

    # R403：面向欧盟用户但数据存中国境内 -> 中（GDPR 跨境规则适用）
    if a["eu_users"] and a["storage_location"] == "中国境内":
        hits.append(_hit(
            "R403", "跨境传输",
            "欧盟用户数据传输回中国境内处理",
            "中",
            ["GDPR-44-49"],
            "从欧盟向中国传输个人数据属于 GDPR 意义上的跨境转移，需充分性认定或适当保障措施。",
            "与欧盟侧签署标准合同条款（SCC），或在欧盟境内部署处理节点，评估数据本地化方案。",
        ))

    # R404：数据存储在欧盟境内 -> 低（GDPR 直接适用）
    if a["storage_location"] == "欧盟境内" and a["collect_personal"]:
        hits.append(_hit(
            "R404", "跨境传输",
            "数据存储在欧盟境内并收集个人信息",
            "低",
            ["GDPR-12-14", "GDPR-17"],
            "业务直接适用 GDPR，需满足其透明度与用户权利要求。",
            "确认隐私政策包含 GDPR 要求的全部要素，并提供英文版本供欧盟用户使用。",
        ))

    # ================= 维度五：第三方管理 =================

    # R501：向第三方共享但未公示 SDK 清单 -> 中
    if a["share_third_party"] and a.get("sdk_disclosed") is not True:
        hits.append(_hit(
            "R501", "第三方管理",
            "向第三方共享数据，但未公示第三方/SDK 清单",
            "中",
            ["PIPL-23", "GDPR-12-14"],
            "接入广告、统计等 SDK 却未告知接收方名称和处理目的，属于未履行告知义务。",
            "在隐私政策中公开第三方 SDK/服务清单（名称、收集的信息、用途），向第三方提供个人信息需取得单独同意。",
        ))

    # R502：未与第三方签数据处理协议 -> 中
    if a["share_third_party"] and a.get("third_party_agreement") is not True:
        hits.append(_hit(
            "R502", "第三方管理",
            "未与第三方签署数据处理协议",
            "中",
            ["PIPL-23"],
            "未以协议约束接收方的处理目的和方式，出现泄露时责任难以厘清。",
            "与全部第三方签署数据处理协议，约定处理目的、期限、安全措施和违约责任，并监督其履行。",
        ))

    # R503：第三方管理完善 -> 低（保持）
    if a["share_third_party"] and a.get("sdk_disclosed") is True and a.get("third_party_agreement") is True:
        hits.append(_hit(
            "R503", "第三方管理",
            "第三方共享管理较为完善",
            "低",
            ["PIPL-23"],
            "清单公示与协议约束均已具备。",
            "保持 SDK 清单及时更新，定期核查第三方实际收集行为与披露一致。",
        ))

    # ================= 维度六：未成年人保护 =================

    # R601：涉及 14 岁以下未成年人且无监护人同意机制 -> 高
    if a["minors_under_14"] and a.get("guardian_consent") is not True:
        hits.append(_hit(
            "R601", "未成年人保护",
            "涉及 14 岁以下未成年人数据，但未取得监护人同意",
            "高",
            ["PIPL-31", "GDPR-8"],
            "处理不满十四周岁未成年人个人信息必须取得其父母或监护人同意，并制定专门的处理规则。",
            "上线监护人同意机制（如监护人身份验证、短信/邮件确认），并单独制定未成年人个人信息处理规则。",
        ))

    # R602：未成年人保护机制已具备 -> 低（提醒）
    if a["minors_under_14"] and a.get("guardian_consent") is True:
        hits.append(_hit(
            "R602", "未成年人保护",
            "未成年人数据已设监护人同意机制",
            "低",
            ["PIPL-31", "GDPR-8"],
            "监护人同意机制已具备，仍需专门处理规则与专人负责。",
            "制定专门的未成年人个人信息处理规则，设置专人负责未成年人信息保护，最小化收集范围。",
        ))

    # ================= 维度七：综合管理 =================

    # R701：日活 10 万以上 -> 中（指定个人信息保护负责人）
    if a["dau_scale"] in ("10万+", "100万+") and a["collect_personal"]:
        hits.append(_hit(
            "R701", "综合管理",
            "日活 10 万以上，个人信息处理规模较大",
            "中",
            ["PIPL-52"],
            "处理个人信息达到规定数量的处理者，应当指定个人信息保护负责人并公开联系方式。",
            "指定个人信息保护负责人，负责监督个人信息处理活动，并在隐私政策中公开其联系方式。",
        ))

    # R702：大规模处理敏感信息 -> 中（个人信息保护影响评估）
    if a["dau_scale"] in ("10万+", "100万+") and a["collect_sensitive"]:
        hits.append(_hit(
            "R702", "综合管理",
            "大规模处理敏感个人信息，需开展影响评估",
            "中",
            ["PIPL-55", "GDPR-35"],
            "处理敏感个人信息等高风险活动，事前应当进行个人信息保护影响评估并留存记录。",
            "开展个人信息保护影响评估（PIA），评估处理目的的合法性与安全风险，评估报告至少保存三年。",
        ))

    # R703：声明不收集个人信息 -> 低（间接标识符提醒）
    if not a["collect_personal"]:
        hits.append(_hit(
            "R703", "综合管理",
            "声明不收集用户个人信息",
            "低",
            ["GDPR-12-14", "PIPL-17"],
            "注意设备标识符、IP 地址、日志信息等间接标识符在多数法域下仍可能构成个人信息。",
            "复核埋点、崩溃日志、第三方 SDK 的实际采集行为，确认确实不触及个人信息；如有收集应及时补充告知。",
        ))

    # R704：强监管行业处理敏感信息 -> 低（行业要求提醒）
    if a["industry"] in ("医疗健康", "金融") and a["collect_sensitive"]:
        hits.append(_hit(
            "R704", "综合管理",
            f"{a['industry']}行业处理敏感个人信息",
            "低",
            ["PIPL-29", "DSL-21"],
            "医疗健康、金融属于强监管行业，还需满足行业主管部门的专门数据规范。",
            "对照行业规范（如金融数据安全分级指南、健康医疗数据安全指南）开展专项自查。",
        ))

    # R8：全部合规 -> 低风险 + 保持建议（仅在前述规则均未命中时输出）
    if not hits:
        hits = [_hit(
            "R8", "综合管理",
            "未发现明显违规情形",
            "低",
            ["PIPL-17", "GDPR-12-14"],
            "当前问卷结果未发现明显违规情形，整体合规状况良好。",
            "保持现有合规措施，法规更新或业务变化（新功能、新 SDK、用户量增长）后重新自查。",
        )]

    # 按风险等级 高->中->低 排序，同级按规则编号排序
    hits.sort(key=lambda h: (LEVEL_ORDER[h["level"]], h["rule_id"]))
    return hits


def summarize_articles(hits):
    """汇总命中记录涉及的全部法条（去重，保持出现顺序），供报告使用。"""
    seen, ordered = set(), []
    for h in hits:
        for art in h["articles"]:
            if art not in seen:
                seen.add(art)
                ordered.append(art)
    return ordered


def compute_dimension_scores(hits):
    """计算七大维度得分：每维 100 起始，按维度内命中扣分，下限 0。

    返回：dict，{维度名: 得分}，供仪表盘雷达图使用。
    """
    scores = {d: 100 for d in DIMENSIONS}
    for h in hits:
        dim = h.get("dimension")
        if dim in scores:
            scores[dim] = max(0, scores[dim] - LEVEL_DEDUCT[h["level"]])
    return scores
