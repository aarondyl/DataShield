"""供 Local Tenant Agent 使用的法规网关，只读本地 SQLite 缓存。"""
import json
from .cache import LocalRegulationCache

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
