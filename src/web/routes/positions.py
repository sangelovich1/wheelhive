from fastapi import APIRouter, Depends, Query
from web.auth import require_auth
from web.config import settings
from web import deps

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

@router.get("/accounts")
def accounts():
    db = deps.get_db()
    return {"username": settings.username,
            "accounts": deps.list_accounts(db, settings.username)}
