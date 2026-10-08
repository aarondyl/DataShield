"""真实 HTTP 验收：Cloud 变更 → Local SQLite → Tenant Agent → Finding。"""
import socket
import threading

from fastapi import FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import uvicorn

from app.db.base import Base
from app.local_regulations.cache import LocalRegulationCache
from app.local_regulations.client import CloudSyncClient
from app.models import (Company, Finding, LegalUnit, LocalReevaluationTask, Product, ProductTwinFact,
    ProductTwinVersion, Regulation, RegulationChange, RegulationEvent, RegulationVersion, Requirement)
from app.tenant.agent.nodes import load_context, persist, retrieve_requirements
from app.understanding.schemas import FindingStatus


def _port():
    sock=socket.socket(); sock.bind(("127.0.0.1", 0)); port=sock.getsockname()[1]; sock.close(); return port


def test_cloud_http_sync_to_local_finding(tmp_path, monkeypatch):
    cloud_engine=create_engine(f"sqlite:///{tmp_path/'cloud.db'}", connect_args={"check_same_thread": False})
    local_engine=create_engine(f"sqlite:///{tmp_path/'datashield.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(cloud_engine); Base.metadata.create_all(local_engine)
    Cloud, Local=sessionmaker(bind=cloud_engine), sessionmaker(bind=local_engine)
    with Cloud() as db:
        reg=Regulation(name="EU AI Act", jurisdiction="EU", official_identifier="EU:AI", canonical_source_url="https://eur-lex.europa.eu/eli/reg/2024/1689/oj")
        db.add(reg); db.flush()
        ver=RegulationVersion(regulation_id=reg.id, version_number=1, normalized_text="Article 50", content_hash="a"*64, is_current=True)
        db.add(ver); db.flush(); reg.current_version_id=ver.id
        unit=LegalUnit(version_id=ver.id, unit_type="article", unit_number="Article 50", path="50", text="Providers shall inform users about AI.")
        db.add(unit); db.flush()
        req=Requirement(regulation_id=reg.id, version_id=ver.id, legal_unit_id=unit.id, requirement_type="obligation", subject_type="provider", action_type="inform", object_type="AI", summary="Provide AI transparency disclosure", conditions_json=[], exceptions_json=[], confidence=.9, status="ACTIVE")
        db.add(req); db.flush()
        change=RegulationChange(regulation_id=reg.id, to_version_id=ver.id, legal_unit_id=unit.id, change_type="ADDED", new_text=unit.text, semantic_summary="新增 AI 告知", materiality="HIGH", requirement_ids=[req.id])
        db.add(change); db.flush()
        db.add(RegulationEvent(event_id="evt_http", regulation_id=reg.id, version_id=ver.id, payload={"materiality":"HIGH", "topics":["AI"]}))
        db.commit()
    with Local() as db:
        company=Company(name="本地租户", target_markets=["EU"]); db.add(company); db.flush()
        product=Product(company_id=company.id, name="本地 AI 产品", target_markets=["EU"]); db.add(product); db.flush()
        twin=ProductTwinVersion(product_id=product.id, version_number=1, reason="test"); db.add(twin); db.flush()
        db.add_all([
            ProductTwinFact(version_id=twin.id, group_name="market_clues", name="EU", status="PRESENT", confidence=.9, source_kind="USER", evidence=[{}], scan_scope={"complete": True}, confirmation_status="CONFIRMED"),
            ProductTwinFact(version_id=twin.id, group_name="subject_types", name="provider", status="PRESENT", confidence=.9, source_kind="USER", evidence=[{}], scan_scope={"complete": True}, confirmation_status="CONFIRMED"),
            ProductTwinFact(version_id=twin.id, group_name="features", name="ai_features", status="PRESENT", confidence=.9, source_kind="USER", evidence=[{}], scan_scope={"complete": True}, confirmation_status="CONFIRMED"),
            ProductTwinFact(version_id=twin.id, group_name="controls", name="ai_disclosure", status="NOT_DETECTED", confidence=.8, source_kind="REPOSITORY", evidence=[{}], scan_scope={"complete": False}, confirmation_status="UNREVIEWED"),
        ]); db.commit()

    # 使用实际 Cloud 路由，uvicorn 经由 TCP 提供同步接口。
    from app.api import regintel
    from app.db.session import get_db
    cloud=FastAPI(); cloud.include_router(regintel.router, prefix="/api")
    def cloud_db():
        db=Cloud()
        try: yield db
        finally: db.close()
    cloud.dependency_overrides[get_db]=cloud_db
    port=_port(); server=uvicorn.Server(uvicorn.Config(cloud, host="127.0.0.1", port=port, log_level="error"))
    thread=threading.Thread(target=server.run, daemon=True); thread.start()
    while not server.started: pass
    monkeypatch.setenv("RUNTIME_MODE", "local"); monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    from app.core.config import get_settings
    get_settings.cache_clear()
    # 图节点显式使用这份 Local SQLite；生产环境则是同一全局 Local SessionLocal。
    monkeypatch.setattr(load_context, "SessionLocal", Local); monkeypatch.setattr(retrieve_requirements, "SessionLocal", Local); monkeypatch.setattr(persist, "SessionLocal", Local)
    import app.db.session as session_module
    monkeypatch.setattr(session_module, "SessionLocal", Local)
    cache=LocalRegulationCache(tmp_path/"datashield.db")
    try:
        assert CloudSyncClient(f"http://127.0.0.1:{port}", cache, session_factory=Local).sync() == 1
    finally:
        server.should_exit=True; thread.join(timeout=5); get_settings.cache_clear()
    with Local() as db:
        assert db.scalar(select(Regulation).where(Regulation.official_identifier == "EU:AI")) is not None
        task=db.scalar(select(LocalReevaluationTask)); assert task.status == "COMPLETED", task.error
        finding=db.scalar(select(Finding)); assert finding is not None
        assert finding.requirement_links and finding.evidence_links
        assert finding.requirement_links[0].requirement_id == finding.evidence_links[0].requirement_id
        requirement = db.get(Requirement, finding.requirement_links[0].requirement_id)
        assert requirement.subject_type == "provider"
        assert requirement.object_type == "AI"
        assert requirement.confidence == .9
        assert finding.evidence_links[0].evidence_snapshot_json["source_url"] == "https://eur-lex.europa.eu/eli/reg/2024/1689/oj"
        tenant_id, product_id, finding_id = finding.tenant_id, finding.product_id, finding.id
        original_twin_id = db.scalar(select(ProductTwinVersion.id))
        requirement_id = requirement.id

    # 此处仍是明确的测试夹具与 mock；验证同步所得数据继续完成业务闭环。
    from fastapi.testclient import TestClient
    from app.main import create_app, enforce_local_runtime_token
    monkeypatch.setenv("RUNTIME_TOKEN", "integration-test-token")
    get_settings.cache_clear()
    # 使用当前 Local 模式构造，避免受先运行的 Cloud 契约测试模块缓存影响。
    app = create_app()
    app.middleware("http")(enforce_local_runtime_token)
    def local_db():
        with Local() as db:
            yield db
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = local_db
    try:
        client = TestClient(app, headers={"X-Runtime-Token": "integration-test-token"})
        detail = client.get(f"/api/v1/findings/{finding_id}", params={"tenant_id": tenant_id})
        assert detail.status_code == 200, detail.text
        assert detail.json()["legal_evidence"] and detail.json()["requirements"]
        assert detail.json()["agent_run"]["model_provider"] == "mock"
        for decision, expected in (("approve", "APPROVED"), ("reject", "REJECTED")):
            created = client.post(f"/api/v1/findings/{finding_id}/remediations", json={
                "tenant_id": tenant_id, "remediation_type": "DOCUMENT_CHANGE", "document_type": "AI transparency notice"})
            assert created.status_code == 201, created.text
            remediation_id = created.json()["remediation"]["id"]
            decided = client.post(f"/api/v1/remediations/{remediation_id}/{decision}", json={"tenant_id": tenant_id})
            assert decided.status_code == 200, decided.text
            assert decided.json()["remediation"]["status"] == expected
        feedback = client.post("/api/v1/feedback", json={"tenant_id": tenant_id, "product_id": product_id,
            "finding_id": finding_id, "feedback_type": "FACT_CORRECTION", "raw_text": "我们已经支持 AI告知，并向用户说明使用人工智能。", "created_by": "integration-test"})
        assert feedback.status_code == 201, feedback.text
        candidate_id = feedback.json()["candidates"][0]["id"]
        confirmed = client.post(f"/api/v1/feedback-candidates/{candidate_id}/confirm", json={"tenant_id": tenant_id})
        assert confirmed.status_code == 200 and confirmed.json()["status"] == "CONFIRMED"
        applied = client.post(f"/api/v1/feedback-candidates/{candidate_id}/apply", json={"tenant_id": tenant_id})
        assert applied.status_code == 200, applied.text
        assert applied.json()["status"] == "APPLIED", applied.text
        assert applied.json()["applied_twin_version_id"] != original_twin_id
        assert applied.json()["reanalysis_run_id"]
        today = client.get("/api/v1/today", params={"tenant_id": tenant_id, "product_id": product_id})
        assert today.status_code == 200, today.text
        assert today.json()["latest_run"]["status"] == "COMPLETED"
        assert today.json()["recently_completed"]
        # 上面的 Cloud TCP 服务已经退出。离线同步失败仍保留法规和画像版本。
        import pytest
        with pytest.raises(ConnectionError):
            CloudSyncClient(f"http://127.0.0.1:{port}", cache, timeout=.1, retries=1, session_factory=Local).sync()
        with Local() as db:
            assert db.get(Finding, finding_id) is not None
            assert db.get(ProductTwinVersion, applied.json()["applied_twin_version_id"]) is not None
            assert db.get(Requirement, requirement_id) is not None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        get_settings.cache_clear()
