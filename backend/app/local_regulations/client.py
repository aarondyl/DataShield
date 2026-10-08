"""仅拉取公开法规的 HTTP 同步客户端。"""
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from .cache import LocalRegulationCache

class CloudSyncClient:
    def __init__(self, base_url: str, cache: LocalRegulationCache, timeout=5, retries=3):
        self.base_url=base_url.rstrip("/"); self.cache=cache; self.timeout=timeout; self.retries=retries
    def get_json(self,path,params):
        url=self.base_url+path+"?"+urlencode(params)
        last=None
        for n in range(self.retries):
            try:
                import json
                with urlopen(url,timeout=self.timeout) as r: return json.load(r)
            except Exception as exc: last=exc; time.sleep(min(.1*(2**n),1))
        raise ConnectionError("法规同步不可用，保留本地缓存") from last
    def sync(self, scope="all", jurisdiction=None):
        cursor,snapshot,_=self.cache.progress(scope); params={"cursor":cursor,"limit":100}
        if snapshot: params["snapshot_cursor"]=snapshot
        if jurisdiction: params["jurisdiction"]=jurisdiction
        while True:
            page=self.get_json("/api/v1/sync/events",params); page["cursor"]=cursor
            bundles=[self.get_json(f"/api/v1/sync/events/{e['event_id']}/bundle",{}) for e in page["events"]]
            self.cache.apply(page,bundles,scope); cursor=page["next_cursor"]
            if not page["has_more"]: return cursor
            params.update(cursor=cursor,snapshot_cursor=page["snapshot_cursor"])
