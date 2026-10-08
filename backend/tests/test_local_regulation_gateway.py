from app.local_regulations.cache import LocalRegulationCache
from app.local_regulations.gateway import LocalRegulationGateway

def test_gateway_reads_only_local_cache(tmp_path):
    c=LocalRegulationCache(tmp_path/"r.db")
    p={"snapshot_cursor":1,"next_cursor":1,"events":[{"id":1,"event_id":"e","payload":{}}]}
    b={"event":{"event_id":"e"},"regulation":{"key":"r"},"version":{"key":"v"},"legal_units":[],"requirements":[{"key":"q","summary":"本地义务"}]}
    c.apply(p,[b]); assert LocalRegulationGateway(c).requirements_for_event("e")[0]["summary"]=="本地义务"
    assert LocalRegulationGateway(c).requirement_contexts_for_event("e")[0].summary=="本地义务"
    assert LocalRegulationGateway(c).trigger("e").event_id=="e"
