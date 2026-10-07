import pytest
from app.understanding.website import analyze_website, public_url
from app.understanding.schemas import WebsiteRequest

def fake_fetch(url, deadline):
    pages = {
        "https://example.com/": '<html><head><title>AI Tool</title></head><body><h1>AI writing platform</h1><a href="/pricing">Pricing</a><a href="/privacy">Privacy</a><input type="email"></body></html>',
        "https://example.com/pricing": '<html><h1>Pricing</h1><p>Stripe subscription for business</p><script src="https://js.stripe.com/v3"></script></html>',
        "https://example.com/privacy": '<html><h1>Privacy Policy</h1><p>We process email and cookies.</p></html>',
    }
    return (200, "", pages[url]) if url in pages else (404, "", "")

def test_public_url_rejects_unsafe_destinations():
    with pytest.raises(ValueError): public_url("file:///etc/passwd")
    with pytest.raises(ValueError): public_url("http://127.0.0.1/")
    with pytest.raises(ValueError): public_url("http://example.com/?token=secret")

def test_bounded_analysis_and_documents():
    result = analyze_website(WebsiteRequest(url="https://example.com/", max_pages=3), fake_fetch)
    assert result.pages_analyzed == ["https://example.com/", "https://example.com/pricing", "https://example.com/privacy"]
    assert result.product_category == "AI Writing Tool"
    assert result.public_documents["privacy_policy"].present
    assert any(v.name == "Stripe" for v in result.vendors)
    assert next(f for f in result.features if f.name == "subscription").status == "PARTIAL"
    assert result.capabilities["AI_disclosure"].status == "NOT_DETECTED"

def test_page_limit_marks_unknown():
    result = analyze_website(WebsiteRequest(url="https://example.com/", max_pages=1), fake_fetch)
    assert result.coverage_complete is False
    assert result.public_documents["privacy_policy"].status == "UNKNOWN"
    assert result.capabilities["account_deletion"].status == "UNKNOWN"


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:8.8.8.8", "224.0.0.1", "100.64.0.1"])
def test_private_dns_answers_rejected(monkeypatch, address):
    import socket
    from app.understanding.website import public_addresses
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))])
    with pytest.raises(ValueError):
        public_addresses("example.com", 80)


def test_redirect_blocked_before_second_request():
    calls = []
    def fetch(url, deadline):
        calls.append(url)
        return 302, "http://169.254.169.254/latest/", ""
    with pytest.raises(ValueError):
        analyze_website(WebsiteRequest(url="https://example.com/"), fetch)
    assert calls == ["https://example.com/"]


def test_hidden_content_and_document_links_are_not_facts():
    def fetch(url, deadline):
        return 200, "", '<script>OpenAI API_KEY=do-not-return</script><div hidden>Anthropic</div><style>Stripe</style><h1>Home</h1><a href="/privacy">Privacy Policy</a><input type="hidden" value="secret-value">'
    result = analyze_website(WebsiteRequest(url="https://example.com/", max_pages=1), fetch)
    assert not result.vendors
    assert not result.public_documents["privacy_policy"].present
    assert "do-not-return" not in result.model_dump_json()
    assert "secret-value" not in result.model_dump_json()


def test_socket_pins_validated_address(monkeypatch):
    import socket
    import time
    from app.understanding import website
    calls = []
    class Socket:
        def settimeout(self, timeout): pass
        def connect(self, address): calls.append(address)
        def close(self): pass
    class Response:
        status = 200
        def getheader(self, key, default=None):
            return {"Content-Type": "text/html", "Content-Length": "0"}.get(key, default)
        def read1(self, count): return b""
    class Connection:
        def __init__(self, host, port, timeout): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): pass
    monkeypatch.setattr(website, "public_addresses", lambda *a: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))])
    monkeypatch.setattr(socket, "socket", lambda *a: Socket())
    monkeypatch.setattr(website.http.client, "HTTPConnection", Connection)
    assert website.fetch_page("http://example.com/", time.monotonic() + 10)[0] == 200
    assert calls == [("93.184.216.34", 80)]


def test_website_api_lifecycle(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from app.api import website_understanding as api
    from app.understanding.jobs import JobStore, get_store
    monkeypatch.setenv("UNDERSTANDING_API_KEY", "test-key")
    store = JobStore(create_engine(f"sqlite:///{tmp_path / 'jobs.db'}", connect_args={"check_same_thread": False}))
    monkeypatch.setattr(api, "analyze_website", lambda request: analyze_website(request, fake_fetch))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_store] = lambda: store
    client = TestClient(app)
    assert client.post("/v1/analyze-website", json={"url": "https://example.com/"}).status_code == 401
    headers = {"Authorization": "Bearer test-key"}
    result = client.post("/v1/analyze-website", json={"url": "https://example.com/"}, headers=headers)
    assert result.status_code == 202
    assert result.json()["status"] == "PENDING"
    response = client.get("/v1/website-analysis/" + result.json()["analysis_id"], headers=headers)
    assert response.json()["status"] == "COMPLETED"
    payload = response.json()["website_analysis"]
    ids = {e["evidence_id"] for e in payload["evidence"]}
    for group in ("features", "vendors", "target_users", "market_clues"):
        assert all(set(f["evidence_ids"]) <= ids for f in payload[group])
    assert client.post("/v1/analyze-website", json={"url": "http://127.0.0.1/"}, headers=headers).status_code == 400
    assert client.get("/v1/website-analysis/missing", headers=headers).status_code == 404
