"""Private JSON-lines pipe worker in the frozen model environment. No TCP listener."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        os.environ[name] = "1"
    os.environ["COLPALI_SCORES_BACKEND"] = "torch"
    temp = ROOT / "runtime/tmp"
    temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(temp)
    network_attempts = []

    def deny(event, args):
        if event in ("socket.connect", "socket.getaddrinfo"):
            network_attempts.append(event)
            raise RuntimeError("Model network disabled")

    sys.addaudithook(deny)
    pipe = sys.stdout
    print("Model worker: verifying local model identity", file=sys.stderr, flush=True)
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from backend.algorithms.colpali_adapter import ColPaliAdapter
        torch.set_num_threads(4)
        torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        cache = Path.home() / ".cache/huggingface/hub"
        profile_path = ROOT / "configs/colpali_local.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        adapter = ColPaliAdapter(
            cache / ("models--vidore--colpali/snapshots/" + profile["adapter_revision"]),
            cache / ("models--vidore--colpaligemma-3b-mix-448-base/snapshots/" + profile["base_revision"]),
            profile_path)
        print("Model worker: loading verified offline weights", file=sys.stderr, flush=True)
        adapter.load()
        print("Model worker: ready", file=sys.stderr, flush=True)
    region_adapter = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get("kind") == "page":
                import struct
                image = Path(request["image_path"]).resolve(strict=True)
                stem = Path(request["output_stem"]).resolve()
                base = (ROOT / "runtime/corpus/ingest").resolve()
                if (not image.is_relative_to(base) or not stem.is_relative_to(base)
                        or hashlib.sha256(image.read_bytes()).hexdigest() != request["render_sha256"]):
                    raise ValueError()
                start = time.perf_counter()
                with contextlib.redirect_stdout(sys.stderr):
                    tensor = adapter.encode_page(image).cpu().contiguous()
                vector = tensor.float().tolist()
                tensor_path, export_path = stem.with_suffix(".pt"), stem.with_suffix(".json")
                if tensor_path.exists() or export_path.exists():
                    raise ValueError("Refuse overwrite")
                torch.save({"schema": "full-page-features-v1", "encoder_sha256": adapter.profile_id,
                            "render_sha256": request["render_sha256"], "embeddings": tensor,
                            "visual_patch_count": 1024}, tensor_path)
                export_path.write_text(json.dumps(vector, allow_nan=False), encoding="utf-8")
                result = {"id": request["id"], "profile_sha256": adapter.profile_id, "worker_pid": os.getpid(),
                          "tensor_path": tensor_path.relative_to(ROOT).as_posix(),
                          "tensor_sha256": hashlib.sha256(tensor_path.read_bytes()).hexdigest(),
                          "export_path": export_path.relative_to(ROOT).as_posix(),
                          "export_sha256": hashlib.sha256(export_path.read_bytes()).hexdigest(),
                          "embedding_sha256": hashlib.sha256(b"".join(struct.pack("<128f", *row) for row in vector)).hexdigest(), "token_count": 1031, "dimension": 128,
                          "patch_tokens": 1024, "dtype": str(tensor.dtype), "page_forward_count": adapter.page_calls,
                          "query_forward_count": adapter.query_calls, "network_attempts": len(network_attempts),
                          "encode_ms": (time.perf_counter()-start)*1000,
                          "peak_allocated_bytes": torch.cuda.max_memory_allocated()}
                pipe.write(json.dumps(result, allow_nan=False) + "\n")
                pipe.flush()
                continue
            question = request["question"]
            if not isinstance(question, str) or not question.strip() or len(question) > 2000:
                raise ValueError()
            start = time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                vector = adapter.encode_queries([question])[0].float()
            audit = adapter.query_audit[-1]
            # The adapter collects query text for CLI research; discard it here.
            adapter.query_audit.clear()
            result = {"id": request["id"], "profile_sha256": adapter.profile_id,
                      "worker_pid": os.getpid(),
                      "vector": vector.tolist(), "forward_count": adapter.query_calls,
                      "valid_tokens": len(vector), "valid_pad_id_tokens": audit["valid_pad_id_tokens"],
                      "query_sha256": hashlib.sha256(question.encode()).hexdigest(),
                      "encode_ms": (time.perf_counter()-start)*1000,
                      "load_seconds": adapter.load_seconds,
                      "network_attempts": len(network_attempts),
                      "peak_allocated_bytes": torch.cuda.max_memory_allocated()}
            if request.get("kind") == "regions":
                from backend.algorithms.d_adapter import DNoTextAdapter
                if region_adapter is None:
                    region_adapter = DNoTextAdapter()
                if request['region_input']['identity']['encoder_sha256'] != adapter.profile_id:
                    raise ValueError('Region encoder mismatch')
                result['regions'] = region_adapter.rank(request['region_input'], vector.cpu())
            pipe.write(json.dumps(result, allow_nan=False) + "\n")
            pipe.flush()
        except Exception:
            # No request, model path or exception details go back to a caller.
            pipe.write('{"error":"MODEL_UNAVAILABLE"}\n')
            pipe.flush()
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
