import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    username: str
    db_path: str
    password: str
    secret: str

def load_settings() -> Settings:
    return Settings(
        username=os.environ.get("WHEELHIVE_WEB_USERNAME", "sangelovich"),
        db_path=os.environ.get("WHEELHIVE_WEB_DB", "/home/steve/code/wheelhive/trades.db"),
        password=os.environ.get("WHEELHIVE_WEB_PASSWORD", ""),
        secret=os.environ.get("WHEELHIVE_WEB_SECRET", ""),
    )

settings = load_settings()
