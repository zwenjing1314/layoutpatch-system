"""R17-only observations and explicit fault fixtures; never used by formal startup."""
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.db.connection import ROOT
from backend.db.models import Document
from backend.main import create_app
from backend.search.qdrant import Qdrant
from backend.search.settings import SearchSettings

OUT = Path(os.environ["LAYOUTPATCH_WORKSPACE_ACCEPTANCE_DIR"]).resolve()
if OUT != ROOT / "runtime/verification/r17/ui":
    raise ValueError("R17 fixture directory required")


class ObservedQdrant(Qdrant):
    def request(self, method, path, body=None, missing=False):
        if (OUT / "fault-qdrant").exists():
            return Qdrant(SearchSettings(qdrant_url="http://127.0.0.1:9")).request(method, path, body, missing)
        return super().request(method, path, body, missing)

    def query(self, scope, vector, k):
        hits = super().query(scope, vector, k)
        if (OUT / "fault-scope").exists():
            (OUT / "fault-scope").unlink()
            with Session(inner.state.engine) as db, db.begin():
                doc = db.get(Document, scope.pages[0].document_id)
                doc.display_name += "（验收期间名称变化）"
        if (OUT / "delay-response").exists():
            (OUT / "delay-started").write_text("started", encoding="utf-8")
            time.sleep(6)
        return hits


inner = create_app(qdrant=ObservedQdrant(), ingestion_enabled=False)


class ObserveResponses:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.wrapped(scope, receive, send)
        status, parts = None, []

        async def observed(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                parts.append(message.get("body", b""))
            await send(message)

        try:
            await self.wrapped(scope, receive, observed)
        finally:
            path = scope["path"]
            record = {"path": path, "status": status, "method": scope["method"]}
            raw = b"".join(parts)
            if path == "/search":
                try:
                    record["response"] = json.loads(raw)
                except ValueError:
                    record["response"] = "interrupted"
            if path.startswith("/pages/") and status == 200:
                record.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            # No auth bodies, query strings, cookies, CSRF, credentials or PNG payloads.
            with (OUT / "http-observations.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")


app = ObserveResponses(inner)
