"""全局法规智能层种子数据：三部法规（GDPR / 个人信息保护法 / 数据安全法）首版入库。

法规文本来自 ``backend/data/regulations/*.txt``（由官方发布的 docx 规范化而来）。
种子流程：
1. 把原始快照复制为「当前在线来源」（``data/sources/{code}.txt``，模拟官网当前内容）；
2. 为每部法规创建 Regulation + RegulatorySource；
3. 走完整入库流水线（解析 → 版本 1 → 义务提取 → chunking → embedding → 索引）；
4. 同步旧 regulation_articles 表（供分析工作流继续检索真实法条）。

演示「法规更新」时：修改 ``data/sources/{code}.txt`` 后调用
``POST /api/v1/sources/{id}/ingest`` 即可触发变化检测全流程。
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Regulation, RegulatorySource
from app.regintel.adapters import BACKEND_ROOT
from app.regintel.pipeline import run_ingestion

#: 原始快照目录 / 当前在线来源目录（相对 backend 根目录）
_REGULATION_DIR = Path("data/regulations")
_SOURCE_DIR = Path("data/sources")

#: 三部 MVP 法规的配置
_REGULATION_DEFS: list[dict] = [
    {
        "code": "gdpr",
        "name": "GDPR（通用数据保护条例）",
        "title": "General Data Protection Regulation (Regulation (EU) 2016/679)",
        "short_name": "GDPR",
        "official_identifier": "Regulation (EU) 2016/679",
        "jurisdiction": "EU",
        "authority": "European Parliament and Council",
        "document_type": "regulation",
        "original_language": "EN/ZH",
        "description": "欧盟个人数据保护核心法规，适用于向欧盟境内个人提供商品/服务或监测其行为的境外企业。",
        "canonical_source_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        "source_name": "EUR-Lex",
        "parser_type": "gdpr_bilingual",
        "language": "zh",
        "default_subject": "controller",
        "published_at": datetime(2016, 5, 4),
        "effective_at": datetime(2018, 5, 25),
    },
    {
        "code": "pipl",
        "name": "个人信息保护法",
        "title": "中华人民共和国个人信息保护法",
        "short_name": "PIPL",
        "official_identifier": "中华人民共和国主席令第九十一号",
        "jurisdiction": "CN",
        "authority": "全国人民代表大会常务委员会",
        "document_type": "law",
        "original_language": "ZH",
        "description": "中国个人信息保护基础法律，规范个人信息处理活动与跨境提供。",
        "canonical_source_url": "https://www.gov.cn/xinwen/2021-08/20/content_5632486.htm",
        "source_name": "中国政府网",
        "parser_type": "cn_law",
        "language": "zh",
        "default_subject": "个人信息处理者",
        "published_at": datetime(2021, 8, 20),
        "effective_at": datetime(2021, 11, 1),
    },
    {
        "code": "dsl",
        "name": "数据安全法",
        "title": "中华人民共和国数据安全法",
        "short_name": "DSL",
        "official_identifier": "中华人民共和国主席令第八十四号",
        "jurisdiction": "CN",
        "authority": "全国人民代表大会常务委员会",
        "document_type": "law",
        "original_language": "ZH",
        "description": "中国数据安全领域基础法律，确立数据分类分级与重要数据出境管理制度。",
        "canonical_source_url": "https://www.gov.cn/xinwen/2021-06/11/content_5616919.htm",
        "source_name": "中国政府网",
        "parser_type": "cn_law",
        "language": "zh",
        "default_subject": "数据处理者",
        "published_at": datetime(2021, 6, 10),
        "effective_at": datetime(2021, 9, 1),
    },
]


def seed_regintel_if_empty(db: Session) -> bool:
    """若全局法规智能层为空，则把三部 MVP 法规完整入库。

    :return: 是否实际执行了写入
    """
    source_count = db.scalar(select(func.count()).select_from(RegulatorySource)) or 0
    if source_count > 0:
        return False

    for definition in _REGULATION_DEFS:
        code = definition["code"]
        origin = BACKEND_ROOT / _REGULATION_DIR / f"{code}.txt"
        live = BACKEND_ROOT / _SOURCE_DIR / f"{code}.txt"
        live.parent.mkdir(parents=True, exist_ok=True)
        if not live.exists():
            shutil.copyfile(origin, live)

        regulation = Regulation(
            name=definition["name"],
            jurisdiction=definition["jurisdiction"],
            description=definition["description"],
            source_url=definition["canonical_source_url"],
            published_at=definition["published_at"],
            effective_at=definition["effective_at"],
            official_identifier=definition["official_identifier"],
            title=definition["title"],
            short_name=definition["short_name"],
            authority=definition["authority"],
            document_type=definition["document_type"],
            status="in_force",
            original_language=definition["original_language"],
            canonical_source_url=definition["canonical_source_url"],
        )
        db.add(regulation)
        db.flush()

        source = RegulatorySource(
            regulation_id=regulation.id,
            jurisdiction=definition["jurisdiction"],
            authority=definition["authority"],
            source_name=definition["source_name"],
            base_url=definition["canonical_source_url"],
            fetch_url=f"data/sources/{code}.txt",
            source_type="local_file",
            parser_type=definition["parser_type"],
            priority=1,
            polling_interval=86400,
            is_active=True,
        )
        db.add(source)
        db.flush()

        run = run_ingestion(
            db,
            source,
            use_llm=False,  # 种子批量入库走确定性规则提取（快、离线可复现）
            default_subject=definition["default_subject"],
            language=definition["language"],
            sync_legacy=True,
        )
        if run.status != "COMPLETED":
            raise RuntimeError(f"种子法规 {definition['name']} 入库失败：{run.error}")
    return True
