"""One bounded Basic CPU page; read old models, write only this private attempt. No network."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main(request_path):
    request_path = Path(request_path).resolve(strict=True)
    output = request_path.parent
    if not output.is_relative_to((ROOT / "runtime/parsing").resolve()):
        raise ValueError("Invalid worker output")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    config = request["profile"]
    home = output / "home"
    home.mkdir()
    for name in ("HOME", "USERPROFILE", "MINERU_HOME", "HF_HOME", "XDG_CACHE_HOME", "TMP", "TEMP"):
        os.environ[name] = str(home)
    os.environ.update(GRADIO_ANALYTICS_ENABLED="False", MINERU_MODEL_BASE_DIR=str((ROOT / config["model_root"]).resolve().parent),
                      MINERU_MODEL_SOURCE="local", MINERU_MODEL_SMALL_BACKEND="onnx",
                      HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1", PYTHONDONTWRITEBYTECODE="1")
    sys.dont_write_bytecode = True
    receipt = {"status": "failed", "network_attempts": 0, "blocked_network_events": [], "blocked_process_attempts": [], "blocked_writes": 0, "blocked_write_targets": [], "sessions": [], "pid": os.getpid(), "packages": {}}
    started = time.monotonic()

    def guard(event, args):
        if event in ("socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.sendto"):
            receipt["network_attempts"] += 1
            receipt["blocked_network_events"].append(event)
            raise PermissionError("Parser network forbidden")
        if event in ("subprocess.Popen", "os.system"):
            receipt["blocked_process_attempts"].append({"event":event,"executable":Path(str(args[0])).name})
            raise PermissionError("Parser process launch forbidden")
        paths = []
        if event == "open":
            path, mode, flags = args
            if isinstance(path,(str,bytes)) and ((isinstance(mode,str) and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
                paths = [path]
        elif event in ("os.mkdir","os.remove","os.rmdir","os.chmod","os.utime"):
            paths = [args[0]]
        elif event in ("os.rename", "os.replace", "os.link", "os.symlink"):
            paths = list(args[:2])
        for raw in paths:
            path = Path(os.fsdecode(raw)).resolve()
            # Upstream suppresses progress with the Windows null device. It is
            # not a filesystem write; allow only this exact sink, no other device.
            if event == "open" and os.name == "nt" and str(path).lower().rstrip("\\/") == "\\\\.\\nul":
                continue
            if not path.is_relative_to(output):
                receipt["blocked_writes"] += 1
                receipt["blocked_write_targets"].append({"event": event,"path": str(path)})
                raise PermissionError("Parser write outside private attempt forbidden")

    sys.addaudithook(guard)
    try:
        for name in ("mineru","docvortex","onnxruntime"):
            receipt["packages"][name] = metadata.version(name)
            if metadata.version(name) != config[name]:
                raise ValueError("Parser package version mismatch")
        import onnxruntime as ort
        original_init, original_run = ort.InferenceSession.__init__, ort.InferenceSession.run
        session_entries = {}

        def audited_init(session, *args, **kwargs):
            options = kwargs.pop("sess_options", None) or ort.SessionOptions()
            options.intra_op_num_threads, options.inter_op_num_threads = 2,1
            kwargs["sess_options"] = options
            # Explicit CPU provider; no GPU fallback or model switch.
            kwargs["providers"] = ["CPUExecutionProvider"]
            begin = time.monotonic()
            original_init(session, *args, **kwargs)
            model = Path(args[0]).resolve()
            model_root = (ROOT / config["model_root"]).resolve()
            relative = model.relative_to(model_root).as_posix()
            expected = config["model_files"][relative]["sha256"]
            with model.open("rb") as stream:
                actual = hashlib.file_digest(stream,"sha256").hexdigest()
            if actual != expected or session.get_providers() != ["CPUExecutionProvider"]:
                raise ValueError("Actual parser model identity mismatch")
            entry = {"model": relative, "sha256": actual, "providers": session.get_providers(), "load_seconds": time.monotonic()-begin, "forward_calls": 0}
            receipt["sessions"].append(entry)
            session_entries[id(session)] = entry

        def audited_run(session, *args, **kwargs):
            session_entries[id(session)]["forward_calls"] += 1
            return original_run(session,*args,**kwargs)

        ort.InferenceSession.__init__, ort.InferenceSession.run = audited_init, audited_run
        from mineru.model.download import ModelRepo
        # Upstream creates lock files even in local mode. Keep locks in OUR attempt,
        # while model payload paths stay read-only in the existing research library.
        ModelRepo.lock_path = lambda repo: home / "locks" / (repo.local_name + ".lock")
        from mineru.parser import parse
        result = parse(Path(request["pdf_path"]), tier="basic", ocr_mode="auto", image_analysis=False,
                       page_range=str(request["identity"]["page_index"]+1))
        raw = result.to_json().encode("utf-8")
        if len(raw) > config["max_output_bytes"]:
            raise ValueError("Parser output exceeds bound")
        with (output / "raw.json").open("xb") as stream:
            stream.write(raw)
        receipt.update(status="completed", raw_sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=len(raw))
    finally:
        receipt["seconds"] = time.monotonic()-started
        with (output / "receipt.json").open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, allow_nan=False, indent=2)


if __name__ == "__main__":
    main(sys.argv[1])
