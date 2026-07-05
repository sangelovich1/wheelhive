import os
import tempfile

os.environ.setdefault("WHEELHIVE_WEB_PASSWORD", "testpw")
os.environ.setdefault("WHEELHIVE_WEB_SECRET", "test-secret-key")
os.environ.setdefault(
    "WHEELHIVE_WEB_DB",
    os.path.join(tempfile.mkdtemp(prefix="wh-web-test-"), "trades.db"),
)

# Seed an empty schema in the temp DB so endpoint queries hit real (empty)
# tables instead of erroring on missing tables. The domain table classes each
# create their table on init. pytest runs with `src/` on sys.path (CWD=src),
# so these bare imports resolve.
import constants

constants.DATABASE_PATH = os.environ["WHEELHIVE_WEB_DB"]

from db import Db
from trades import Trades
from shares import Shares
from deposits import Deposits
from dividends import Dividends

_seed_db = Db()
for _Table in (Trades, Shares, Deposits, Dividends):
    _Table(_seed_db)
