import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import web.app as appmod
from web.app import create_app


def test_health():
    r = TestClient(create_app()).get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_root_404_when_no_spa_build(monkeypatch):
    # No index.html in STATIC -> the SPA mount is skipped; GET / is a 404,
    # and the API still works.
    empty = tempfile.mkdtemp(prefix="wh-nospa-")
    monkeypatch.setattr(appmod, "STATIC", Path(empty))
    c = TestClient(create_app())
    assert c.get("/").status_code == 404
    assert c.get("/health").json() == {"ok": True}


def test_root_serves_spa_when_built(monkeypatch):
    # With an index.html present in STATIC, GET / serves the SPA shell (200).
    built = tempfile.mkdtemp(prefix="wh-spa-")
    (Path(built) / "index.html").write_text("<!doctype html><title>WheelHive</title>")
    monkeypatch.setattr(appmod, "STATIC", Path(built))
    r = TestClient(create_app()).get("/")
    assert r.status_code == 200
    assert "WheelHive" in r.text


def test_missing_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(appmod, "settings", type(appmod.settings)(
        username="u", db_path="/tmp/x.db", password="p", secret=""
    ))
    import pytest
    with pytest.raises(RuntimeError):
        create_app()


def test_main_reads_port_env(monkeypatch):
    # main() honors WHEELHIVE_WEB_PORT (default 8080) so the service can bind
    # port 80 on the VM without a code change.
    import uvicorn
    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: captured.update(k))
    monkeypatch.setenv("WHEELHIVE_WEB_PORT", "80")
    appmod.main()
    assert captured["port"] == 80

    captured.clear()
    monkeypatch.delenv("WHEELHIVE_WEB_PORT", raising=False)
    appmod.main()
    assert captured["port"] == 8080
