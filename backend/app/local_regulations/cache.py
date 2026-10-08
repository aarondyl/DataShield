"""本地法规缓存：只保存云端公开法规数据，绝不保存或上传私有上下文。"""
import json
import sqlite3
from pathlib import Path


class LocalRegulationCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True); self.path = path
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sync_state (scope TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0, snapshot INTEGER NOT NULL DEFAULT 0, offline INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS cached_events (event_id TEXT PRIMARY KEY, event_seq INTEGER UNIQUE NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cached_regulations (entity_key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cached_versions (entity_key TEXT PRIMARY KEY, regulation_key TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cached_legal_units (entity_key TEXT PRIMARY KEY, version_key TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cached_requirements (entity_key TEXT PRIMARY KEY, version_key TEXT NOT NULL, payload TEXT NOT NULL);
            """)
    def connect(self): return sqlite3.connect(self.path)
    def progress(self, scope="all"):
        with self.connect() as db:
            return db.execute("SELECT cursor,snapshot,offline FROM sync_state WHERE scope=?",(scope,)).fetchone() or (0,0,0)
    def mark_offline(self, scope="all"):
        with self.connect() as db:
            db.execute("INSERT INTO sync_state(scope,cursor,snapshot,offline) VALUES (?,0,0,1) ON CONFLICT(scope) DO UPDATE SET offline=1",(scope,))
    def apply(self, page: dict, bundles: list[dict], scope="all"):
        """同一事务写法规、事件和最后页游标；异常时全部回滚。"""
        required={e["event_id"] for e in page["events"]}
        supplied={b["event"]["event_id"] for b in bundles}
        if len(required) != len(page["events"]) or len(supplied) != len(bundles): raise ValueError("同步页面或 Bundle 存在重复事件")
        if required != supplied: raise ValueError("同步页面与法规 Bundle 不完整")
        ids=[e["id"] for e in page["events"]]
        if ids != sorted(set(ids)): raise ValueError("同步事件必须严格递增且不可重复")
        if any(i > page["snapshot_cursor"] for i in ids): raise ValueError("事件超出固定快照")
        expected=ids[-1] if ids else page.get("cursor", page["next_cursor"])
        if page["next_cursor"] != expected: raise ValueError("next_cursor 必须等于本页最后事件或空页 cursor")
        with self.connect() as db:
            current=db.execute("SELECT cursor,snapshot FROM sync_state WHERE scope=?",(scope,)).fetchone() or (0,0)
            if page["next_cursor"] < current[0]: raise ValueError("同步游标不能倒退")
            if current[1] and page["snapshot_cursor"] < current[1]: raise ValueError("同步快照不能倒退")
            for b in bundles:
                r=b["regulation"]; v=b["version"]
                db.execute("INSERT OR REPLACE INTO cached_regulations VALUES (?,?)",(r["key"],json.dumps(r)))
                db.execute("INSERT OR REPLACE INTO cached_versions VALUES (?,?,?)",(v["key"],r["key"],json.dumps(v)))
                for u in b["legal_units"]: db.execute("INSERT OR REPLACE INTO cached_legal_units VALUES (?,?,?)",(u["key"],v["key"],json.dumps(u)))
                for q in b["requirements"]: db.execute("INSERT OR REPLACE INTO cached_requirements VALUES (?,?,?)",(q["key"],v["key"],json.dumps(q)))
            for e in page["events"]: db.execute("INSERT OR REPLACE INTO cached_events VALUES (?,?,?)",(e["event_id"],e["id"],json.dumps(e)))
            # 完成时清除快照，下一轮可取得新的上界；未完成时保留以恢复分页。
            snapshot = page["snapshot_cursor"] if page.get("has_more") else 0
            db.execute("INSERT INTO sync_state(scope,cursor,snapshot,offline) VALUES (?,?,?,0) ON CONFLICT(scope) DO UPDATE SET cursor=excluded.cursor,snapshot=excluded.snapshot,offline=0",(scope,page["next_cursor"],snapshot))
