from fastapi.testclient import TestClient
from web.app import create_app

def authed_client():
    c = TestClient(create_app())
    c.post("/api/login", json={"password": "testpw"})
    return c

def test_accounts_shape():
    r = authed_client().get("/api/accounts")
    assert r.status_code == 200
    body = r.json()
    assert "accounts" in body and isinstance(body["accounts"], list)
    assert body["username"]

def test_positions_shape():
    r = authed_client().get("/api/positions")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"stocks", "options", "account"}
    assert isinstance(body["stocks"], list) and isinstance(body["options"], list)

def test_summary_shape():
    r = authed_client().get("/api/portfolio/summary")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"options", "dividends", "stocks_unrealized", "year", "account"}
