from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlparse

from backend.db.connection import DEFAULT_DATABASE, database_path


@dataclass(frozen=True)
class AuthSettings:
    database: Path = DEFAULT_DATABASE
    origin: str = "http://127.0.0.1:3000"
    secure: bool = False
    idle_seconds: int = 1800
    absolute_seconds: int = 28800
    cookie_name: str = "layoutpatch_session"

    def __post_init__(self):
        database_path(self.database)
        origin = urlparse(self.origin)
        if origin.scheme not in ("http", "https") or not origin.netloc or origin.path or origin.query or origin.fragment or origin.username:
            raise ValueError("APP_ORIGIN must be a single origin without path or credentials")
        if not self.secure and origin.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Non-loopback deployment requires Secure cookies")
        if origin.scheme == "https" and not self.secure:
            raise ValueError("HTTPS requires Secure cookies")
        if not 0 < self.idle_seconds <= self.absolute_seconds:
            raise ValueError("Invalid session lifetimes")

    @classmethod
    def from_environment(cls):
        # Real process environment only; no generic dotenv reader or secret export.
        flag = os.getenv("SESSION_COOKIE_SECURE", "false").lower()
        if flag not in ("true", "false"):
            raise ValueError("SESSION_COOKIE_SECURE must be true or false")
        return cls(database=Path(os.getenv("LAYOUTPATCH_DATABASE_PATH", str(DEFAULT_DATABASE))),
                   origin=os.getenv("APP_ORIGIN", "http://127.0.0.1:3000"), secure=flag == "true")
