from datetime import date

from fastapi import APIRouter, Depends, Query
from df_stats import DFStats
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

@router.get("/portfolio/summary")
def summary(account: str | None = Query(default=None), year: int | None = Query(default=None)):
    db = deps.get_db()
    yr = year or date.today().year
    stats = DFStats(db)
    stats.load(username=settings.username, account=account or None)
    stats.filter_by_year(yr)
    stats_dict = stats.as_dict()  # {"monthly": [...], "totals": {...}}
    totals = stats_dict.get("totals", {})
    pos = deps.get_positions(db)
    stocks = pos.get_stock_positions(settings.username, account or None)
    unrealized = round(sum(float(s.get("unrealized_pl", 0.0)) for s in stocks), 2)
    return {
        "account": account or None,
        "year": yr,
        "options": totals,
        "dividends": {"total": float(totals.get("Dividends", 0.0))},
        "stocks_unrealized": unrealized,
        "monthly": stats_dict.get("monthly", []),
    }
