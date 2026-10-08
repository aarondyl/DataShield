from app.local_regulations.cache import LocalRegulationCache

def test_cache_commits_cursor_with_bundle_atomically(tmp_path):
    c=LocalRegulationCache(tmp_path/"regulations.db")
    page={"snapshot_cursor":7,"next_cursor":7,"events":[{"id":7,"event_id":"evt_7"}]}
    bundle={"regulation":{"key":"EU:GDPR"},"version":{"key":"EU:GDPR:v2"},"legal_units":[{"key":"u"}],"requirements":[{"key":"r"}]}
    c.apply(page,[bundle]); assert c.progress()==(7,7,0)
    with c.connect() as db: assert db.execute("select count(*) from cached_requirements").fetchone()[0]==1
