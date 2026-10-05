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
