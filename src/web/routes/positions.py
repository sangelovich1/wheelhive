from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException
from df_stats import DFStats
from web.auth import require_auth
from web.config import settings
from web import deps

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


def _resolve_account(db, account: str | None) -> str | None:
    """Return a validated account or None (all accounts). Rejects unknown
    accounts so user input never reaches raw SQL in the domain layer."""
    if not account:
        return None
    if account not in deps.list_accounts(db, settings.username):
        raise HTTPException(status_code=400, detail="unknown account")
    return account

@router.get("/accounts")
def accounts():
    db = deps.get_db()
    return {"username": settings.username,
            "accounts": deps.list_accounts(db, settings.username)}

@router.get("/positions")
def positions(account: str | None = Query(default=None)):
    db = deps.get_db()
    acct = _resolve_account(db, account)
    pos = deps.get_positions(db)
    return {
        "account": acct,
        "stocks": pos.get_stock_positions(settings.username, acct),
        "options": pos.get_open_options(settings.username, acct),
    }

@router.get("/portfolio/summary")
def summary(account: str | None = Query(default=None), year: int | None = Query(default=None)):
    db = deps.get_db()
    acct = _resolve_account(db, account)
    yr = year or date.today().year
    stats = DFStats(db)
    stats.load(username=settings.username, account=acct)
    stats.filter_by_year(yr)
    stats_dict = stats.as_dict()  # {"monthly": [...], "totals": {...}}
    totals = stats_dict.get("totals", {})
    pos = deps.get_positions(db)
    stocks = pos.get_stock_positions(settings.username, acct)
    unrealized = round(sum(float(s.get("unrealized_pl", 0.0)) for s in stocks), 2)
    return {
        "account": acct,
        "year": yr,
        "options": totals,
        "dividends": {"total": float(totals.get("Dividends", 0.0))},
        "stocks_unrealized": unrealized,
        "monthly": stats_dict.get("monthly", []),
    }
