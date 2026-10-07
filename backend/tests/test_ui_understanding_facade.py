import hashlib
from fastapi import BackgroundTasks,HTTPException
import pytest
from app.api import ui_understanding

def test_owner_is_server_derived_and_never_returned(monkeypatch):
    monkeypatch.setenv("UNDERSTANDING_API_KEY","server-only-secret")
    assert ui_understanding._owner()==hashlib.sha256(b"server-only-secret").hexdigest()
    assert "server-only-secret" not in ui_understanding._owner()

def test_facade_requires_server_configuration(monkeypatch):
    monkeypatch.delenv("UNDERSTANDING_API_KEY",raising=False)
    with pytest.raises(HTTPException) as error: ui_understanding._owner()
    assert error.value.status_code==503

def test_facade_exposes_only_scoped_browser_routes():
    paths={route.path for route in ui_understanding.router.routes}
    assert "/v1/ui/understanding/website" in paths
    assert "/v1/ui/understanding/products/{product_id}/twin" in paths
    assert all("key" not in path.casefold() for path in paths)
