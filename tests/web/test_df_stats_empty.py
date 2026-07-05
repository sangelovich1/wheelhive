"""Regression: DFStats.as_dict() must be empty-safe — a period with no activity
returns zero totals instead of raising KeyError on a missing column (Dividends)."""
from datetime import date

from db import Db
from trades import Trades
from shares import Shares
from deposits import Deposits
from dividends import Dividends
from df_stats import DFStats


def _empty_db() -> Db:
    db = Db(in_memory=True)
    for table in (Trades, Shares, Deposits, Dividends):
        table(db)
    return db


def test_as_dict_empty_returns_zero_totals():
    stats = DFStats(_empty_db())
    stats.load(username="nobody", account=None)
    stats.filter_by_year(date.today().year)
    result = stats.as_dict()
    assert set(result) >= {"monthly", "totals"}
    assert result["monthly"] == []
    for key in ("STO", "BTC", "BTO", "STC", "Premium", "Dividends"):
        assert result["totals"][key] == 0.0
