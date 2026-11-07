"""R19 real backend with explicit bounded isolation-only gates and safe observations."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time

from backend.db.connection import ROOT
from backend.documents.pipeline import IngestError
from backend.main import create_app
from backend.search.qdrant import Qdrant

OUT = Path(os.environ["LAYOUTPATCH_R19_ACCEPTANCE_DIR"]).resolve()
if OUT != ROOT / "runtime/verification/r19/ui":
    raise RuntimeError("R19 isolated directory required")


def append(name, value):
    with (OUT / name).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def gate(name, job_id=None):
    if not (OUT / name).exists():
        return
    event = {"gate": name, "job_id": job_id, "time": time.time()}
    (OUT / ("reached-" + name + ".json")).write_text(json.dumps(event), encoding="utf-8")
    append("gate-events.jsonl", event)
    deadline = time.monotonic() + 180
    while (OUT / name).exists():
        if time.monotonic() >= deadline:
            raise IngestError("INGEST_DEADLINE_EXCEEDED")
        time.sleep(.1)


class ObservedQdrant(Qdrant):
    def request(self, method, path, body=None, missing=False):
        if method == "POST" and path.endswith("/points/query"):
            append("qdrant-filters.jsonl", {"filter": body.get("filter"), "limit": body.get("limit")})
        return super().request(method, path, body, missing)


inner = create_app(qdrant=ObservedQdrant(), ingestion_enabled=True)
runner = inner.state.ingestion
original_render = runner.renderer
original_checkpoint = runner.checkpoint
original_run = runner.run_one


def render(*args):
    result = original_render(*args)
    if (OUT / "fail-render-once").exists():
        (OUT / "fail-render-once").unlink()
        append("gate-events.jsonl", {"gate": "explicit-render-failure-after-real-CPU-render", "time": time.time()})
        raise IngestError("RENDER_FAILED")
    gate("hold-after-render")
    return result


def checkpoint(job_id, stage=None, progress=None, **kwargs):
    original_checkpoint(job_id, stage, progress, **kwargs)
    if stage == "activating":
        gate("hold-before-activation", job_id)


def run_one():
    return False if (OUT / "pause-claim").exists() else original_run()


runner.renderer, runner.checkpoint, runner.run_one = render, checkpoint, run_one


class ObserveResponses:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, status, chunks = scope["path"], None, []
        delayed = False

        async def observed(message):
            nonlocal status, delayed
            if message["type"] == "http.response.start":
                status = message["status"]
                if path == "/index" and (OUT / "delay-upload-response").exists():
                    (OUT / "delay-upload-response").unlink()
                    delayed = True
                    append("gate-events.jsonl", {"gate": "delay-upload-response-after-persist", "time": time.time()})
                    await asyncio.sleep(8)
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, receive, observed)
        finally:
            record = {"path": path, "method": scope["method"], "status": status, "time": time.time(), "delayed": delayed}
            body = b"".join(chunks)
            if path in ("/index", "/jobs", "/documents", "/search") or path.startswith("/jobs/"):
                try:
                    record["response"] = json.loads(body)
                except ValueError:
                    record["response"] = "interrupted"
            if path.startswith("/pages/") and status == 200:
                record.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            # Never capture auth response/body, request headers, cookies, passwords or CSRF.
            append("http-observations.jsonl", record)


app = ObserveResponses(inner)
