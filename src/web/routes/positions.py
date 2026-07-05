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

@router.get("/positions")
def positions(account: str | None = Query(default=None)):
    db = deps.get_db()
    pos = deps.get_positions(db)
    acct = account or None
    return {
        "account": acct,
        "stocks": pos.get_stock_positions(settings.username, acct),
        "options": pos.get_open_options(settings.username, acct),
    }
