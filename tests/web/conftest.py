import os
import tempfile

os.environ.setdefault("WHEELHIVE_WEB_PASSWORD", "testpw")
os.environ.setdefault("WHEELHIVE_WEB_SECRET", "test-secret-key")
os.environ.setdefault(
    "WHEELHIVE_WEB_DB", os.path.join(tempfile.mkdtemp(prefix="wh-web-test-"), "trades.db")
)
