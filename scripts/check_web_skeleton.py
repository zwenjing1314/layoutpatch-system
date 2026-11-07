"""Real local HTTP/lifecycle check. Run after yarn build, with ports 3000/8000 free."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runtime/verification/r05"
OUT.mkdir(parents=True, exist_ok=True)
evidence = {"date": "2026-11-06", "scope": "1B-1 real HTTP; no browser interaction or business checks", "checks": []}
owned = []

def free(port):
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0

def request(path):
    try:
        with urlopen(path, timeout=5) as response:
            return response.status, dict(response.headers), response.read().decode()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read().decode()

def wait(url):
    for _ in range(80):
        try:
            result = request(url)
            if result[0] == 200:
                return result
        except (OSError, URLError):
            pass
        time.sleep(.25)
    raise RuntimeError(f"Not ready: {url}")

def launch(name, command, cwd):
    stream = (OUT / f"{name}-{len(owned)}.log").open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                               env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"})
    owned.append((process, stream))
    return process

def stop(process):
    if process.poll() is None:
        # Only terminate the exact process tree created by this check.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True, capture_output=True)
        process.wait(timeout=10)

def record(name, ok, detail):
    evidence["checks"].append({"name": name, "passed": ok, "detail": detail})
    if not ok:
        raise AssertionError(name)

try:
    if not all(free(port) for port in (3000, 8000)):
        raise RuntimeError("Ports occupied; no existing process will be stopped")
    for cycle in (1, 2):
        backend = launch("backend", [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1"], ROOT)
        frontend = launch("frontend", [shutil.which("node"), "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"], ROOT / "frontend")
        direct = wait("http://127.0.0.1:8000/health")
        proxy = wait("http://127.0.0.1:3000/api/health")
        page = wait("http://127.0.0.1:3000")
        record(f"cycle{cycle}_health_and_proxy", json.loads(direct[2]) == json.loads(proxy[2]) == {"status": "ok"}, "Direct and same-origin proxy HTTP 200 with identical JSON")
        record(f"cycle{cycle}_no_store", proxy[1].get("cache-control", proxy[1].get("Cache-Control")) == "no-store", "Proxy preserves no-store header")
        record(f"cycle{cycle}_shell", "视觉文档检索" in page[2] and "检查连接" in page[2], "Production HTML contains shell and button")
        spec = json.loads(request("http://127.0.0.1:8000/openapi.json")[2])
        expected = {"/health", "/auth/login", "/auth/me", "/auth/logout", "/auth/password", "/admin/profiles"}
        record(f"cycle{cycle}_routes", set(spec["paths"]) == expected, "Only health, auth and read-only profiles; no retrieval routes")
        stop(backend)
        failure = request("http://127.0.0.1:3000/api/health")
        record(f"cycle{cycle}_backend_outage", failure[0] >= 500, f"Backend stopped: proxy HTTP {failure[0]}")
        stop(frontend)
        for _ in range(40):
            if all(free(port) for port in (3000, 8000)):
                break
            time.sleep(.1)
        record(f"cycle{cycle}_stopped", all(free(port) for port in (3000, 8000)), "Owned processes stopped; ports released")
finally:
    for process, stream in owned:
        stop(process)
        stream.close()
    (ROOT / "docs/checks/stage1b-1-web.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(evidence, ensure_ascii=False, indent=2))
