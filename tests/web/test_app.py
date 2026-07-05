from fastapi.testclient import TestClient
from web.app import create_app


def test_health():
    r = TestClient(create_app()).get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_health_when_no_spa_build():
    # No static/index.html yet -> the SPA mount is skipped and the app still
    # builds and serves the API. GET / should 404 (no SPA), not error.
    r = TestClient(create_app()).get("/")
    assert r.status_code == 404
