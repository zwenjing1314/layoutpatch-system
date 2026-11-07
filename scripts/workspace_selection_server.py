"""R18 observations/explicit delays around real endpoints; never formal startup."""
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs

from backend.db.connection import ROOT
from backend.main import create_app
from backend.search.qdrant import Qdrant
from backend.search.settings import SearchSettings

OUT = Path(os.environ["LAYOUTPATCH_R18_ACCEPTANCE_DIR"]).resolve()
if OUT != ROOT / "runtime/verification/r18/ui":
    raise RuntimeError("R18 isolated directory required")


class ObservedQdrant(Qdrant):
    def request(self, method, path, body=None, missing=False):
        if (OUT / "fault-qdrant").exists():
            return Qdrant(SearchSettings(qdrant_url="http://127.0.0.1:9")).request(method, path, body, missing)
        if method == "POST" and path.endswith("/points/query"):
            with (OUT / "qdrant-filters.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"filter": body.get("filter"), "limit": body.get("limit")}) + "\n")
        return super().request(method, path, body, missing)

    def query(self, scope, vector, k):
        hits = super().query(scope, vector, k)
        if (OUT / "delay-search").exists():
            (OUT / "delay-search").unlink()
            (OUT / "search-delay-started").write_text("started", encoding="utf-8")
            time.sleep(5)
        return hits


inner = create_app(qdrant=ObservedQdrant(), ingestion_enabled=False)


class ObserveResponses:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http": return await self.wrapped(scope, receive, send)
        path, status, parts = scope["path"], None, []
        params = parse_qs(scope.get("query_string", b"").decode())
        delayed = False

        async def observed(message):
            nonlocal status, delayed
            if message["type"] == "http.response.start":
                status = message["status"]
                if path == "/documents" and (OUT / "delay-list").exists():
                    (OUT / "delay-list").unlink(); delayed = True
                    (OUT / "list-delay-started").write_text("started", encoding="utf-8")
                    await asyncio.sleep(3)
            elif message["type"] == "http.response.body": parts.append(message.get("body", b""))
            await send(message)

        try:
            await self.wrapped(scope, receive, observed)
        finally:
            record = {"path": path, "status": status, "method": scope["method"], "delayed": delayed}
            raw = b"".join(parts)
            if path in ("/search", "/documents"):
                record["params"] = {key: values for key, values in params.items() if key in ("q", "k", "document_id", "name", "limit")}
                record["has_cursor"] = "cursor" in params
                try: record["response"] = json.loads(raw)
                except ValueError: record["response"] = "interrupted"
            if path.startswith("/pages/") and status == 200:
                record.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            # Private observations only: no auth body/header/cookie/password/CSRF.
            with (OUT / "http-observations.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")


app = ObserveResponses(inner)
