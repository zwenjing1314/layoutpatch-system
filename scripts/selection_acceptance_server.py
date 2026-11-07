"""Isolated R16 server: audit real Qdrant filter arguments, never question/vector/secrets."""
import json
import os
from pathlib import Path
from uuid import uuid4

from backend.db.connection import ROOT
from backend.main import create_app
from backend.search.qdrant import Qdrant


class AuditedQdrant(Qdrant):
    def request(self, method, path, body=None, missing=False):
        result = super().request(method, path, body, missing)
        if method == "POST" and path.endswith("/points/query"):
            directory = Path(os.environ["LAYOUTPATCH_SELECTION_AUDIT_DIR"]).resolve()
            if not directory.is_relative_to(ROOT / "runtime/verification/r16"):
                raise ValueError("Acceptance audit outside R16 runtime")
            directory.mkdir(parents=True, exist_ok=True)
            safe = {key: body[key] for key in ("filter", "limit", "using", "params", "with_payload", "with_vector")}
            (directory / (uuid4().hex + ".json")).write_text(json.dumps(safe), encoding="utf-8")
        return result


app = create_app(qdrant=AuditedQdrant(), ingestion_enabled=False)
