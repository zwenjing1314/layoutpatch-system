"""One persistent model child per backend, serialized with bounded waiting."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
import os
from pathlib import Path
import subprocess
import threading
import uuid

from backend.db.connection import ROOT
from .qdrant import SearchUnavailable, validate_vector
from .settings import SearchSettings


class SearchBusy(SearchUnavailable):
    pass


class ModelWorker:
    def __init__(self, settings=None):
        self.settings = settings or SearchSettings.from_environment()
        self.lock = threading.Lock()
        self.process = None
        self.log = None
        self.last_audit = None

    def _stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                else:
                    self.process.kill()
            self.process.wait(timeout=10)
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None

    def close(self):
        with self.lock:
            self._stop()

    def encode(self, question, expected_profile):
        result = self._call({"question": question}, expected_profile)
        return result["vector"]

    def encode_page(self, image_path, output_stem, render_sha256, expected_profile):
        return self._call({"kind": "page", "image_path": str(image_path), "output_stem": str(output_stem),
                           "render_sha256": render_sha256}, expected_profile)

    def _call(self, payload, expected_profile):
        if not self.lock.acquire(timeout=self.settings.queue_timeout):
            raise SearchBusy("Model busy")
        reader = ThreadPoolExecutor(max_workers=1)
        try:
            if self.process is None:
                folder = ROOT / "runtime/logs"
                folder.mkdir(parents=True, exist_ok=True)
                self.log = (folder / "model-worker.log").open("a", encoding="utf-8")
                self.process = subprocess.Popen([str(self.settings.model_python), "-B", "-u",
                    str(ROOT / "scripts/model_query_worker.py")], cwd=ROOT, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=self.log, text=True, encoding="utf-8",
                    env={**os.environ, "PYTHONUTF8": "1"}, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if self.process.poll() is not None:
                raise SearchUnavailable("Model stopped")
            request_id = uuid.uuid4().hex
            self.process.stdin.write(json.dumps({"id": request_id, **payload}) + "\n")
            self.process.stdin.flush()
            line = reader.submit(self.process.stdout.readline).result(timeout=self.settings.worker_timeout)
            result = json.loads(line)
            if result.get("id") != request_id or result.get("profile_sha256") != expected_profile or result.get("network_attempts") != 0:
                raise ValueError()
            if payload.get("kind") == "page":
                if result.get("token_count") != 1031 or result.get("dimension") != 128 or result.get("patch_tokens") != 1024:
                    raise ValueError()
            else:
                validate_vector(result["vector"])
            self.last_audit = {k: v for k, v in result.items() if k not in ("vector", "id")}
            audit_dir = os.getenv("LAYOUTPATCH_PAGE_AUDIT_DIR" if payload.get("kind") == "page" else "LAYOUTPATCH_QUERY_AUDIT_DIR")
            if audit_dir:
                folder = Path(audit_dir).resolve()
                if not folder.is_relative_to(ROOT / "runtime"):
                    raise ValueError("Audit must stay inside runtime")
                folder.mkdir(parents=True, exist_ok=True)
                # Explicit local verification only; no question text, cookie or credentials.
                (folder / f"{request_id}.json").write_text(json.dumps(result, allow_nan=False), encoding="utf-8")
            return result
        except (OSError, ValueError, KeyError, TypeError, AttributeError, TimeoutError, SearchUnavailable):
            self._stop()
            raise SearchUnavailable("Model unavailable") from None
        finally:
            reader.shutdown(wait=False, cancel_futures=True)
            self.lock.release()
