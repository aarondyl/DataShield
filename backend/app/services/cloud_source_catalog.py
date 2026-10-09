"""幂等维护 Cloud 的首批官方法规来源目录。

目录记录的是可信发布机构的原始入口，不代表已下载、解析或经法律人员核验。
版本在采集时统一标记 UNREVIEWED，直到未来的人工审核流程明确更新状态。
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Regulation, RegulatorySource


OFFICIAL_SOURCES = (
    {
        "identifier": "PIPL-2021",
        "jurisdiction": "CN",
        "authority": "全国人民代表大会常务委员会",
        "name": "中华人民共和国个人信息保护法",
        "short_name": "PIPL",
        "title": "中华人民共和国个人信息保护法",
        "canonical_url": "https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm",
        "fetch_url": "https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm",
        "parser_type": "cn_law",
        "original_language": "ZH",
        "published_at": datetime(2021, 8, 20),
        "effective_at": datetime(2021, 11, 1),
        "description": "全国人大网公布的法律全文，由国家互联网信息办公室转载。自动采集版本须经人工核验。",
    },
    {
        "identifier": "DSL-2021",
        "jurisdiction": "CN",
        "authority": "全国人民代表大会常务委员会",
        "name": "中华人民共和国数据安全法",
        "short_name": "DSL",
        "title": "中华人民共和国数据安全法",
        "canonical_url": "https://www.cac.gov.cn/2021-06/11/c_1624994566919140.htm",
        "fetch_url": "https://www.cac.gov.cn/2021-06/11/c_1624994566919140.htm",
        "parser_type": "cn_law",
        "original_language": "ZH",
        "published_at": datetime(2021, 6, 10),
        "effective_at": datetime(2021, 9, 1),
        "description": "全国人大网公布的法律全文，由国家互联网信息办公室转载。自动采集版本须经人工核验。",
    },
    {
        "identifier": "EU-2016-679",
        "jurisdiction": "EU",
        "authority": "European Parliament and Council of the European Union",
        "name": "General Data Protection Regulation",
        "short_name": "GDPR",
        "title": "Regulation (EU) 2016/679",
        "canonical_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679",
        "fetch_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679",
        "parser_type": "gdpr_bilingual",
        "original_language": "EN",
        "published_at": datetime(2016, 5, 4),
        "effective_at": datetime(2018, 5, 25),
        "active": False,
        "description": "EUR-Lex 官方法律文本入口。自动采集版本须经人工核验。",
    },
)


def seed_cloud_official_sources(db: Session) -> int:
    """按官方文号幂等创建法规与来源记录，不覆盖已有内容或状态。"""
    created = 0
    for item in OFFICIAL_SOURCES:
        regulation = db.scalar(
            select(Regulation).where(Regulation.official_identifier == item["identifier"])
        )
        if regulation is None:
            regulation = Regulation(
                official_identifier=item["identifier"],
                name=item["name"],
                title=item["title"],
                short_name=item["short_name"],
                jurisdiction=item["jurisdiction"],
                authority=item["authority"],
                document_type="law" if item["jurisdiction"] == "CN" else "regulation",
                status="in_force",
                original_language=item["original_language"],
                published_at=item["published_at"],
                effective_at=item["effective_at"],
                source_url=item["canonical_url"],
                canonical_source_url=item["canonical_url"],
                description=item["description"],
            )
            db.add(regulation)
            db.flush()
            created += 1

        source = db.scalar(
            select(RegulatorySource).where(
                RegulatorySource.regulation_id == regulation.id,
                RegulatorySource.fetch_url == item["fetch_url"],
            )
        )
        if source is None:
            db.add(
                RegulatorySource(
                    regulation_id=regulation.id,
                    jurisdiction=item["jurisdiction"],
                    authority=item["authority"],
                    source_name=item["short_name"],
                    base_url=item["canonical_url"],
                    fetch_url=item["fetch_url"],
                    source_type="html",
                    parser_type=item["parser_type"],
                    priority=10,
                    polling_interval=86400,
                    is_active=item.get("active", True),
                )
            )
            created += 1
    db.commit()
    return created
