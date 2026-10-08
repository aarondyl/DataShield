"""供 Local Tenant Agent 使用的法规网关，只读本地 SQLite 缓存。"""
import json
import hashlib
from .cache import LocalRegulationCache
from app.tenant.regulatory.schemas import RequirementContext

class LocalRegulationGateway:
    def __init__(self, cache: LocalRegulationCache): self.cache=cache
    def requirements_for_event(self, event_id: str) -> list[dict]:
        with self.cache.connect() as db:
            row=db.execute("SELECT payload FROM cached_events WHERE event_id=?",(event_id,)).fetchone()
            if not row: return []
            event=json.loads(row[0]); keys=set((event.get("payload") or {}).get("requirement_keys", []))
            rows=db.execute("SELECT payload FROM cached_requirements").fetchall()
        values=[json.loads(r[0]) for r in rows]
        return [r for r in values if not keys or r["key"] in keys]

    @staticmethod
    def _local_id(key: str) -> int:
        """稳定本地关联标识；不复用云端数据库自增主键。"""
        return int(hashlib.sha256(key.encode()).hexdigest()[:15], 16)

    def requirement_contexts_for_event(self, event_id: str) -> list[RequirementContext]:
        """将缓存法规适配为既有 Tenant Agent 合同。"""
        result=[]
        for item in self.requirements_for_event(event_id):
            key=item["key"]; unit=item.get("legal_unit_key")
            result.append(RequirementContext(
                id=self._local_id(key), regulation_id=0, version_id=self._local_id(item.get("version_key", "local")),
                legal_unit_id=self._local_id(unit) if unit else None, requirement_type=item.get("type", "obligation"),
                subject_type="", action_type=item.get("action", ""), object_type="", conditions=item.get("conditions", []),
                exceptions=item.get("exceptions", []), summary=item.get("summary", ""), confidence=0.8,
                status=item.get("status", "ACTIVE"), regulation_name="本地法规缓存", jurisdiction="", regulation_version=None, source_url="",
            ))
        return result
