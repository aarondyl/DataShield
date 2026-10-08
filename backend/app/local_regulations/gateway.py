"""供 Local Tenant Agent 使用的法规网关，只读本地 SQLite 缓存。"""
import json
from .cache import LocalRegulationCache
from app.tenant.regulatory.schemas import RequirementContext
from app.tenant.regulatory.schemas import RegulationSourceContext, RegulationTrigger, LegalEvidence

class LocalRegulationGateway:
    def __init__(self, cache: LocalRegulationCache, session_factory=None):
        self.cache=cache; self.session_factory=session_factory
    def requirements_for_event(self, event_id: str) -> list[dict]:
        with self.cache.connect() as db:
            row=db.execute("SELECT version_key FROM cached_event_bundles WHERE event_id=?",(event_id,)).fetchone()
            if not row: return []
            rows=db.execute("SELECT payload FROM cached_requirements WHERE version_key=?",(row[0],)).fetchall()
        values=[json.loads(r[0]) for r in rows]
        return values

    def _session_factory(self):
        if self.session_factory is not None: return self.session_factory
        from app.db.session import SessionLocal
        return SessionLocal

    def requirement_contexts_for_event(self, event_id: str) -> list[RequirementContext]:
        """将缓存法规适配为既有 Tenant Agent 合同。"""
        from sqlalchemy import select
        from app.models import LocalRegulationBinding, Requirement, Regulation, RegulationVersion
        keys=[item["key"] for item in self.requirements_for_event(event_id)]
        if not keys: return []
        with self._session_factory()() as db:
            bindings=db.scalars(select(LocalRegulationBinding).where(
                LocalRegulationBinding.entity_type == "requirement",
                LocalRegulationBinding.entity_key.in_(keys),
            )).all()
            ids=[row.local_id for row in bindings]
            rows=db.scalars(select(Requirement).where(Requirement.id.in_(ids))).all()
            result=[]
            for req in rows:
                regulation=db.get(Regulation, req.regulation_id); version=db.get(RegulationVersion, req.version_id)
                result.append(RequirementContext(id=req.id, regulation_id=req.regulation_id, version_id=req.version_id,
                    legal_unit_id=req.legal_unit_id, requirement_type=req.requirement_type, subject_type=req.subject_type,
                    action_type=req.action_type, object_type=req.object_type, conditions=req.conditions_json,
                    exceptions=req.exceptions_json, summary=req.summary, confidence=req.confidence, status=req.status,
                    regulation_name=regulation.name if regulation else "", jurisdiction=regulation.jurisdiction if regulation else "",
                    regulation_version=version.version_number if version else None, source_url=regulation.canonical_source_url if regulation else ""))
            return result

    def trigger(self, event_id: str) -> RegulationTrigger:
        with self.cache.connect() as db:
            row=db.execute("SELECT payload FROM cached_events WHERE event_id=?",(event_id,)).fetchone()
        if not row: raise ValueError("本地法规缓存中不存在该事件")
        event=json.loads(row[0]); payload=event.get("payload") or {}
        contexts=self.requirement_contexts_for_event(event_id)
        if not contexts: raise ValueError("本地法规缓存中不存在该事件对应的有效 Requirement")
        return RegulationTrigger(event_id=event_id,event_type=event.get("event_type","regulation.change.ready"),
          regulation_id=contexts[0].regulation_id,version_id=contexts[0].version_id,change_ids=[],requirement_ids=[x.id for x in contexts],legal_unit_ids=[x.legal_unit_id for x in contexts if x.legal_unit_id],payload=payload,
          materiality=payload.get("materiality","LOW"),topics=payload.get("topics",[]),change_summaries=[],source=RegulationSourceContext())

    def evidence_for(self, requirements: list[RequirementContext]) -> list[LegalEvidence]:
        from app.models import LegalUnit, Regulation, RegulationVersion
        result=[]
        with self._session_factory()() as db:
            for req in requirements:
                if req.legal_unit_id is None: continue
                unit=db.get(LegalUnit, req.legal_unit_id); regulation=db.get(Regulation, req.regulation_id); version=db.get(RegulationVersion, req.version_id)
                if unit and regulation and version:
                    result.append(LegalEvidence(legal_unit_id=unit.id, regulation_id=regulation.id, regulation_name=regulation.name, version_id=version.id, version=version.version_number, article=unit.unit_number, heading=unit.heading, content=unit.text, source_url=regulation.canonical_source_url, requirement_ids=[req.id]))
        return result
