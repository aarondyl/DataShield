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
    def apply(self, page: dict, bundles: list[dict], scope="all"):
        """同一事务写法规、事件和最后页游标；异常时全部回滚。"""
        with self.connect() as db:
            for b in bundles:
                r=b["regulation"]; v=b["version"]
                db.execute("INSERT OR REPLACE INTO cached_regulations VALUES (?,?)",(r["key"],json.dumps(r)))
                db.execute("INSERT OR REPLACE INTO cached_versions VALUES (?,?,?)",(v["key"],r["key"],json.dumps(v)))
                for u in b["legal_units"]: db.execute("INSERT OR REPLACE INTO cached_legal_units VALUES (?,?,?)",(u["key"],v["key"],json.dumps(u)))
                for q in b["requirements"]: db.execute("INSERT OR REPLACE INTO cached_requirements VALUES (?,?,?)",(q["key"],v["key"],json.dumps(q)))
            for e in page["events"]: db.execute("INSERT OR REPLACE INTO cached_events VALUES (?,?,?)",(e["event_id"],e["id"],json.dumps(e)))
            db.execute("INSERT INTO sync_state(scope,cursor,snapshot,offline) VALUES (?,?,?,0) ON CONFLICT(scope) DO UPDATE SET cursor=excluded.cursor,snapshot=excluded.snapshot,offline=0",(scope,page["next_cursor"],page["snapshot_cursor"]))
