from app.local_regulations.cache import LocalRegulationCache

def test_cache_commits_cursor_with_bundle_atomically(tmp_path):
    c=LocalRegulationCache(tmp_path/"regulations.db")
    page={"snapshot_cursor":7,"next_cursor":7,"events":[{"id":7,"event_id":"evt_7"}]}
    bundle={"event":{"event_id":"evt_7"},"regulation":{"key":"EU:GDPR"},"version":{"key":"EU:GDPR:v2"},"legal_units":[{"key":"u"}],"requirements":[{"key":"r"}]}
    c.apply(page,[bundle]); assert c.progress()==(7,7,0)
    with c.connect() as db: assert db.execute("select count(*) from cached_requirements").fetchone()[0]==1

def test_cache_rejects_incomplete_or_backward_page(tmp_path):
    c=LocalRegulationCache(tmp_path/"r.db")
    page={"snapshot_cursor":2,"next_cursor":2,"events":[{"id":2,"event_id":"e2"}]}
    try: c.apply(page,[])
    except ValueError: pass
    else: assert False
