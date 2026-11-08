"""Offline file/implementation verification in model env, without loading weights or inference."""
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys


def main():
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    def deny(event, args):
        if event in ("socket.connect", "socket.getaddrinfo"):
            raise RuntimeError("Network disabled")
    sys.addaudithook(deny)
    from backend.algorithms.colpali_adapter import ColPaliAdapter, file_sha256
    from colpali_engine.models import ColPali, ColPaliProcessor
    profile_path = Path(__file__).resolve().parents[1] / "configs/colpali_local.json"
    profile = json.loads(profile_path.read_text("utf-8"))
    cache = Path.home() / ".cache/huggingface/hub"
    adapter = ColPaliAdapter(cache / ("models--vidore--colpali/snapshots/" + profile["adapter_revision"]),
        cache / ("models--vidore--colpaligemma-3b-mix-448-base/snapshots/" + profile["base_revision"]), profile_path, device="cpu")
    for name, cls in (("ColPali", ColPali), ("ColPaliProcessor", ColPaliProcessor)):
        if file_sha256(Path(inspect.getfile(cls))) != profile["historical_implementation_sha256"][name]:
            raise ValueError("Implementation identity mismatch")
    print(json.dumps({"encoder_sha256": adapter.profile_id, "verified_files": len(adapter.verified_files),
        "implementation_count": 2, "network_attempts": 0, "inference_count": 0}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print('{"error":"ENCODER_IDENTITY_MISMATCH"}')
        raise SystemExit(1)
