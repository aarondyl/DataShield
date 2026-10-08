"""本地法规缓存：只保存云端公开法规数据，绝不保存或上传私有上下文。"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


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
            CREATE TABLE IF NOT EXISTS cached_event_bundles (event_id TEXT PRIMARY KEY, regulation_key TEXT NOT NULL, version_key TEXT NOT NULL);
            """)
            columns={row[1] for row in db.execute("PRAGMA table_info(sync_state)")}
            for name in ("last_success_at", "last_attempt_at", "last_error"):
                if name not in columns: db.execute(f"ALTER TABLE sync_state ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
    def connect(self): return sqlite3.connect(self.path)
    def progress(self, scope="all"):
        with self.connect() as db:
            return db.execute("SELECT cursor,snapshot,offline FROM sync_state WHERE scope=?",(scope,)).fetchone() or (0,0,0)
    def mark_offline(self, scope="all"):
        with self.connect() as db:
            now=datetime.now(timezone.utc).isoformat()
            db.execute("INSERT INTO sync_state(scope,cursor,snapshot,offline,last_attempt_at,last_error) VALUES (?,0,0,1,?,?) ON CONFLICT(scope) DO UPDATE SET offline=1,last_attempt_at=excluded.last_attempt_at,last_error=excluded.last_error",(scope,now,"法规同步不可用，正在使用本地缓存"))

    def status(self, scope="all"):
        with self.connect() as db:
            row=db.execute("SELECT cursor,snapshot,offline,last_success_at,last_attempt_at,last_error FROM sync_state WHERE scope=?",(scope,)).fetchone()
        return dict(zip(("cursor","snapshot","offline","last_success_at","last_attempt_at","last_error"), row or (0,0,0,"","","")))

    def events(self, limit=100):
        with self.connect() as db:
            rows=db.execute("SELECT event_id,event_seq,payload FROM cached_events ORDER BY event_seq DESC LIMIT ?",(limit,)).fetchall()
            bundles={row[0]: (row[1], row[2]) for row in db.execute("SELECT event_id,regulation_key,version_key FROM cached_event_bundles")}
            regulations={row[0]: json.loads(row[1]) for row in db.execute("SELECT entity_key,payload FROM cached_regulations")}
        return [{"event": json.loads(payload), "sequence": sequence, "regulation": regulations.get(bundles.get(event_id,("", ""))[0], {}), "version_key": bundles.get(event_id,("", ""))[1]} for event_id,sequence,payload in rows]
    def _validate(self, page: dict, bundles: list[dict], current: tuple[int, int]):
        required={e["event_id"] for e in page["events"]}
        supplied={b["event"]["event_id"] for b in bundles}
        if len(required) != len(page["events"]) or len(supplied) != len(bundles): raise ValueError("同步页面或 Bundle 存在重复事件")
        if required != supplied: raise ValueError("同步页面与法规 Bundle 不完整")
        ids=[e["id"] for e in page["events"]]
        if ids != sorted(set(ids)): raise ValueError("同步事件必须严格递增且不可重复")
        if any(i > page["snapshot_cursor"] for i in ids): raise ValueError("事件超出固定快照")
        expected=ids[-1] if ids else page.get("cursor", page["next_cursor"])
        if page["next_cursor"] != expected: raise ValueError("next_cursor 必须等于本页最后事件或空页 cursor")
        if page["next_cursor"] < current[0]: raise ValueError("同步游标不能倒退")
        if current[1] and page["snapshot_cursor"] < current[1]: raise ValueError("同步快照不能倒退")

    def apply(self, page: dict, bundles: list[dict], scope="all", *, db=None,
              materialize: Callable[[dict], None] | None = None):
        """单事务写缓存、ORM 物化和 cursor。

        传入 SQLAlchemy Session 时绝不自行提交；调用者可把本地实体和任务一起回滚。
        """
        if db is None:
            with self.connect() as conn:
                self._apply(conn.execute, page, bundles, scope, materialize)
            return
        conn = db.connection()
        self._apply(lambda sql, params=(): conn.exec_driver_sql(sql, params), page, bundles, scope, materialize)

    def _apply(self, execute, page: dict, bundles: list[dict], scope: str, materialize):
        current = execute("SELECT cursor,snapshot FROM sync_state WHERE scope=?", (scope,)).fetchone() or (0, 0)
        self._validate(page, bundles, current)
        for b in bundles:
            r, v = b["regulation"], b["version"]
            execute("INSERT OR REPLACE INTO cached_regulations VALUES (?,?)", (r["key"], json.dumps(r)))
            execute("INSERT OR REPLACE INTO cached_versions VALUES (?,?,?)", (v["key"], r["key"], json.dumps(v)))
            for u in b["legal_units"]:
                execute("INSERT OR REPLACE INTO cached_legal_units VALUES (?,?,?)", (u["key"], v["key"], json.dumps(u)))
            for q in b["requirements"]:
                execute("INSERT OR REPLACE INTO cached_requirements VALUES (?,?,?)", (q["key"], v["key"], json.dumps(q)))
            execute("INSERT OR REPLACE INTO cached_event_bundles VALUES (?,?,?)", (b["event"]["event_id"], r["key"], v["key"]))
            if materialize is not None:
                materialize(b)
        for e in page["events"]:
            execute("INSERT OR REPLACE INTO cached_events VALUES (?,?,?)", (e["event_id"], e["id"], json.dumps(e)))
        snapshot = page["snapshot_cursor"] if page.get("has_more") else 0
        now=datetime.now(timezone.utc).isoformat()
        execute("INSERT INTO sync_state(scope,cursor,snapshot,offline,last_success_at,last_attempt_at,last_error) VALUES (?,?,?,0,?,?, '') ON CONFLICT(scope) DO UPDATE SET cursor=excluded.cursor,snapshot=excluded.snapshot,offline=0,last_success_at=excluded.last_success_at,last_attempt_at=excluded.last_attempt_at,last_error=''", (scope, page["next_cursor"], snapshot, now, now))
