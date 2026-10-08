"""仅拉取公开法规的 HTTP 同步客户端。"""
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .cache import LocalRegulationCache

class CloudSyncClient:
    def __init__(self, base_url: str, cache: LocalRegulationCache, timeout=5, retries=3, session_factory=None):
        self.base_url=base_url.rstrip("/"); self.cache=cache; self.timeout=timeout; self.retries=retries
        self.session_factory=session_factory
    def get_json(self,path,params):
        url=self.base_url+path+"?"+urlencode(params)
        last=None
        for n in range(self.retries):
            try:
                import json
                request = Request(url, headers={"X-DataShield-Api-Version": "1.0"})
                with urlopen(request,timeout=self.timeout) as r: return json.load(r)
            except Exception as exc: last=exc; time.sleep(min(.1*(2**n),1))
        raise ConnectionError("法规同步不可用，保留本地缓存") from last
    def sync(self, scope="all", jurisdiction=None):
        scope = f"{scope}:jurisdiction={jurisdiction or '*'}"
        cursor,snapshot,_=self.cache.progress(scope); params={"cursor":cursor,"limit":100}
        if snapshot: params["snapshot_cursor"]=snapshot
        if jurisdiction: params["jurisdiction"]=jurisdiction
        while True:
            try: page=self.get_json("/api/v1/sync/events",params)
            except ConnectionError:
                self.cache.mark_offline(scope); raise
            page["cursor"]=cursor
            try:
                bundles=[self.get_json(f"/api/v1/sync/events/{e['event_id']}/bundle",{}) for e in page["events"]]
            except ConnectionError:
                self.cache.mark_offline(scope)
                raise
            self._commit_page(page, bundles, scope); cursor=page["next_cursor"]
            if not page["has_more"]:
                from app.local_regulations.tasks import run_pending
                run_pending(self.session_factory)
                return cursor
            params.update(cursor=cursor,snapshot_cursor=page["snapshot_cursor"])

    def _commit_page(self, page, bundles, scope):
        """缓存、物化、重评估任务和游标必须使用同一个 SQLite 提交。"""
        if self.session_factory is None:
            from app.db.session import SessionLocal
            session_factory = SessionLocal
        else:
            session_factory = self.session_factory
        from sqlalchemy import select
        from app.local_regulations.materializer import materialize_bundle
        from app.local_regulations.tasks import enqueue
        from app.models import Product
        with session_factory() as db:
            with db.begin():
                self.cache.apply(page, bundles, scope, db=db, materialize=lambda bundle: materialize_bundle(db, bundle))
                product_ids = list(db.scalars(select(Product.id)).all())
                for event in page["events"]:
                    enqueue(db, event["event_id"], product_ids)
