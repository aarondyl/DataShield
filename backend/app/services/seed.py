"""种子数据：ABC Technology / SmartWatch X1 / 预置法规条款。

启动时（RUN_SEED=true 且 companies 表为空）写入。
法规条款内容为**准确的通行摘要**（1-3 句），并以 ``[DEMO SUMMARY]`` 前缀明确标注，
避免被误认为法规原文。入库同时完成向量化与索引构建，检索立即可用。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Product
from app.rag.ingestion import ingest_regulation_text

#: 条款内容统一前缀：明确标注为演示用摘要而非原文
DEMO_PREFIX = "[DEMO SUMMARY] "

# ---------------------------------------------------------------------------
# 预置法规：准确通行摘要（非原文），按"条款号 -> (标题, 摘要, 主题)"组织
# ---------------------------------------------------------------------------

_GDPR_ARTICLES: list[tuple[str, str, str, str]] = [
    (
        "第4条",
        "定义",
        "「个人数据」指与已识别或可识别自然人相关的任何信息；「处理」涵盖收集、记录、存储、使用、传输、删除等几乎全部操作。",
        "定义",
    ),
    (
        "第5条",
        "个人数据处理原则",
        "处理个人数据须遵循合法、公平、透明、目的限制、数据最小化、准确性、存储期限限制、完整性与保密性原则；控制者须能证明合规（问责制）。",
        "处理原则",
    ),
    (
        "第6条",
        "处理的合法性基础",
        "处理个人数据须具备六项合法性基础之一：数据主体同意、履行合同所必需、履行法定义务、保护重大利益、执行公共任务、控制者合法利益。",
        "合法性基础",
    ),
    (
        "第9条",
        "特殊类别个人数据的处理",
        "原则上禁止处理揭示种族、政治观点、宗教信仰、工会身份、基因数据、生物识别数据、健康数据、性生活等特殊类别个人数据；仅在明示同意、劳动社保法义务、重大公共利益等法定例外下方可处理。",
        "特殊类别数据",
    ),
    (
        "第32条",
        "处理的安全性",
        "控制者与处理者须采取与风险相适应的技术与组织措施（如假名化、加密、系统可用性与韧性保障、定期测试评估），确保处理安全。",
        "数据安全",
    ),
    (
        "第35条",
        "数据保护影响评估",
        "当处理可能给自然人权利自由带来高风险时（尤其涉及大规模处理特殊类别数据或系统性监控），控制者须在处理前开展数据保护影响评估（DPIA）。",
        "影响评估",
    ),
    (
        "第44条",
        "跨境传输的一般原则",
        "向第三国或国际组织传输个人数据，仅在充分性认定、适当保障措施（如标准合同条款）等本章条件满足时方可进行，且不得损害本条例规定的保护水平。",
        "跨境传输",
    ),
]

_PIPL_ARTICLES: list[tuple[str, str, str, str]] = [
    (
        "第13条",
        "处理个人信息的合法性基础",
        "处理个人信息须具备下列情形之一：取得个人同意、订立或履行合同及人力资源管理所必需、履行法定职责义务、应对突发公共卫生事件、公共利益新闻报道、合理处理已公开信息或其他法定情形。",
        "合法性基础",
    ),
    (
        "第17条",
        "告知义务",
        "处理个人信息前，须以显著方式、清晰易懂的语言，真实、准确、完整地告知处理者名称与联系方式、处理目的与方式、信息种类、保存期限、个人权利行使方式等事项。",
        "告知同意",
    ),
    (
        "第29条",
        "敏感个人信息的处理",
        "处理敏感个人信息（生物识别、宗教信仰、特定身份、医疗健康、金融账户、行踪轨迹及不满十四周岁未成年人个人信息等）须取得个人的单独同意，并具备特定的目的和充分的必要性。",
        "敏感个人信息",
    ),
    (
        "第31条",
        "未成年人个人信息",
        "处理不满十四周岁未成年人个人信息，须取得其父母或其他监护人的同意，并制定专门的个人信息处理规则。",
        "未成年人保护",
    ),
    (
        "第38条",
        "个人信息跨境提供",
        "因业务需要向境外提供个人信息的，须通过国家网信部门安全评估、专业机构认证、订立标准合同或满足其他法定条件之一，并保障境外接收方处理活动达到本法保护标准。",
        "跨境传输",
    ),
]

_DSL_ARTICLES: list[tuple[str, str, str, str]] = [
    (
        "第21条",
        "数据分类分级保护制度",
        "国家建立数据分类分级保护制度，根据数据的重要程度及遭破坏后的危害程度实行分类分级保护；对重要数据实行重点保护，各地区、各部门须制定重要数据目录。",
        "分类分级",
    ),
    (
        "第31条",
        "重要数据出境管理",
        "关键信息基础设施运营者在境内运营中收集和产生的重要数据出境，适用网络安全法规定的安全评估；其他数据处理者的重要数据出境管理办法由国家网信部门会同有关部门制定。",
        "跨境传输",
    ),
]


def _articles_to_text(regulation_name: str, articles: list[tuple[str, str, str, str]]) -> str:
    """把 (条款号, 标题, 摘要, 主题) 列表拼成可被 chunking 切分的法规文本。"""
    blocks = [f"{number} {title}\n{DEMO_PREFIX}{summary}" for number, title, summary, _ in articles]
    return f"{regulation_name}\n\n" + "\n\n".join(blocks)


def _topics_of(articles: list[tuple[str, str, str, str]]) -> dict[str, str]:
    """生成 {条款号: 主题} 映射。"""
    return {number: topic for number, _, _, topic in articles}


def seed_if_empty(db: Session) -> bool:
    """若 companies 表为空则写入全部种子数据。

    :return: 是否实际执行了写入
    """
    company_count = db.scalar(select(func.count()).select_from(Company)) or 0
    if company_count > 0:
        return False

    # ===== 企业：ABC Technology =====
    company = Company(
        name="ABC Technology",
        industry="消费电子",
        country="中国",
        target_markets=["Germany", "France"],
        business_model="智能硬件研发与销售（B2C），配套移动应用与云服务",
    )
    db.add(company)
    db.flush()

    # ===== 产品：SmartWatch X1 =====
    db.add(
        Product(
            company_id=company.id,
            name="SmartWatch X1",
            category="智能穿戴",
            target_markets=["Germany", "France"],
            collects_personal_data=True,
            collects_sensitive_data=True,
            collects_health_data=True,
            collects_location_data=False,
            children_related=False,
            third_party_data_sharing=True,
            has_privacy_policy=False,
            cross_border_data_transfer=True,
            description="智能手表：采集心率、睡眠等健康数据，配套 App 注册账号体系，数据回传中国云端并与第三方分析服务共享。",
        )
    )
    db.commit()

    # ===== 法规：GDPR / 个人信息保护法 / 数据安全法 =====
    ingest_regulation_text(
        db,
        name="GDPR（通用数据保护条例）",
        jurisdiction="EU",
        description="欧盟个人数据保护核心法规，适用于向欧盟境内个人提供商品/服务或监测其行为的境外企业。",
        source_url="https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        text=_articles_to_text("GDPR（通用数据保护条例）", _GDPR_ARTICLES),
        article_topics=_topics_of(_GDPR_ARTICLES),
    )
    ingest_regulation_text(
        db,
        name="个人信息保护法",
        jurisdiction="CN",
        description="中国个人信息保护基础法律，规范个人信息处理活动与跨境提供。",
        source_url="https://www.gov.cn/xinwen/2021-08/20/content_5632486.htm",
        text=_articles_to_text("个人信息保护法", _PIPL_ARTICLES),
        article_topics=_topics_of(_PIPL_ARTICLES),
    )
    ingest_regulation_text(
        db,
        name="数据安全法",
        jurisdiction="CN",
        description="中国数据安全领域基础法律，确立数据分类分级与重要数据出境管理制度。",
        source_url="https://www.gov.cn/xinwen/2021-06/11/content_5616919.htm",
        text=_articles_to_text("数据安全法", _DSL_ARTICLES),
        article_topics=_topics_of(_DSL_ARTICLES),
    )
    return True
