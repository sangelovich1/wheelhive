import hmac
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from web.config import settings

router = APIRouter()

class LoginBody(BaseModel):
    password: str

def require_auth(request: Request) -> None:
    if not request.session.get("authed"):
        raise HTTPException(status_code=401, detail="authentication required")

@router.post("/api/login")
def login(body: LoginBody, request: Request):
    if not settings.password or not hmac.compare_digest(body.password, settings.password):
        raise HTTPException(status_code=401, detail="invalid password")
    request.session["authed"] = True
    return {"authenticated": True}

@router.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}

@router.get("/api/session")
def session(request: Request):
    return {"authenticated": bool(request.session.get("authed"))}
