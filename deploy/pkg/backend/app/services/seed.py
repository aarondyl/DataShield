"""种子数据：ABC Technology / SmartWatch X1 + 全局法规智能层（三部 MVP 法规）。

启动时（RUN_SEED=true 且 companies 表为空）写入。
法规部分由 :mod:`app.services.seed_regintel` 通过完整入库流水线写入：
真实法条全文 + 版本 1 + 法律单元树 + 结构化义务 + 向量索引，
同时同步旧 regulation_articles 表供分析工作流检索。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Product
from app.services.seed_regintel import seed_regintel_if_empty


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

    # ===== 法规：GDPR / 个人信息保护法 / 数据安全法（全局法规智能层完整入库）=====
    seed_regintel_if_empty(db)
    return True
