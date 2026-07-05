import constants as const
from db import Db
from shares import Shares
from trades import Trades
from positions import Positions

from web.config import settings


def get_db() -> Db:
    # Db() has no db_path parameter; it opens const.DATABASE_PATH (read at
    # connect time). Point it at the configured DB before opening.
    const.DATABASE_PATH = settings.db_path
    return Db()


def get_positions(db: Db) -> Positions:
    return Positions(db, Shares(db), Trades(db))


def list_accounts(db: Db, username: str) -> list[str]:
    sql = """
      SELECT DISTINCT account FROM (
        SELECT account FROM trades    WHERE username=?
        UNION SELECT account FROM shares    WHERE username=?
        UNION SELECT account FROM deposits  WHERE username=?
        UNION SELECT account FROM dividends WHERE username=?
      ) WHERE account IS NOT NULL
    """
    rows = db.query_parameterized(sql, (username, username, username, username))
    accounts = sorted({r[0] for r in rows})
    if "default" in accounts:
        accounts.remove("default")
        accounts.insert(0, "default")
    return accounts
