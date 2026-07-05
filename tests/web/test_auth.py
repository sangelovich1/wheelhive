from fastapi.testclient import TestClient
from web.app import create_app

def client():
    return TestClient(create_app())

def test_session_unauthed():
    r = client().get("/api/session")
    assert r.status_code == 200
    assert r.json() == {"authenticated": False}

def test_login_wrong_password():
    r = client().post("/api/login", json={"password": "nope"})
    assert r.status_code == 401

def test_login_then_session_ok():
    c = client()
    assert c.post("/api/login", json={"password": "testpw"}).status_code == 200
    assert c.get("/api/session").json() == {"authenticated": True}

def test_protected_requires_auth():
    r = client().get("/api/accounts")
    assert r.status_code == 401
