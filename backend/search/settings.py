from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlparse

from backend.db.connection import ROOT


@dataclass(frozen=True)
class SearchSettings:
    qdrant_url: str = "http://127.0.0.1:6333"
    model_python: Path = ROOT / ".venv/Scripts/python.exe"
    worker_timeout: float = 180
    queue_timeout: float = 5

    def __post_init__(self):
        url = urlparse(self.qdrant_url)
        if url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port or url.path or url.query or url.fragment or url.username:
            raise ValueError("Qdrant must be an explicit local HTTP origin")

    @classmethod
    def from_environment(cls):
        return cls(qdrant_url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"))


def qdrant_key():
    value = os.getenv("QDRANT_API_KEY")
    if value is None:
        # Deliberately read only this one server secret, not generic dotenv settings.
        path = ROOT / ".env"
        lines = path.read_text(encoding="utf-8-sig").splitlines() if path.is_file() else []
        values = [line.split("=", 1)[1].strip() for line in lines if line.startswith("QDRANT_API_KEY=")]
        value = values[0] if len(values) == 1 else ""
    if not value or len(value) < 16:
        raise ValueError("Local Qdrant key is missing")
    return value
