"""Verify the frozen 1A page cache and export float32 JSON for the Web environment."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare(output):
    import torch
    from backend.algorithms.contracts import valid_embedding
    output = output.resolve()
    if not output.is_relative_to(ROOT / "runtime") or output.exists():
        raise ValueError("Output must be a new directory inside project runtime")
    config = json.loads((ROOT / "configs/development_features.json").read_text())
    source = (ROOT / config["source_directory"]).resolve()
    if not source.is_relative_to(ROOT / "runtime"):
        raise ValueError("Source must be inside project runtime")
    for name, expected in config["files"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Feature source hash mismatch")
    manifest_path = ROOT / "runtime/corpus/manifest.json"
    profile_path = ROOT / "configs/colpali_local.json"
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != config["corpus_manifest_sha256"] or hashlib.sha256(profile_path.read_bytes()).hexdigest() != config["encoder_profile_sha256"]:
        raise ValueError("Corpus/profile identity mismatch")
    report = json.loads((source / "report.json").read_text())
    corpus = json.loads(manifest_path.read_text())
    payload = torch.load(source / "page_embeddings.pt", map_location="cpu", weights_only=True)
    expected_ids = [p["page_id"] for p in corpus["pages"]]
    if (report["status"] != "passed" or report["profile_id"] != config["encoder_profile_sha256"]
        or report["corpus_sha256"] != config["corpus_manifest_sha256"] or report["profile"] != json.loads(profile_path.read_text())
        or payload["profile_id"] != report["profile_id"] or payload["page_ids"] != expected_ids
        or len(payload["embeddings"]) != len(expected_ids) or len(set(expected_ids)) != len(expected_ids)
        or len(report["page_encoding"]) != len(expected_ids)):
        raise ValueError("Feature/report mapping mismatch")
    prepared = []
    for page, recorded, tensor in zip(corpus["pages"], report["page_encoding"], payload["embeddings"], strict=True):
        if any(recorded[k] != v for k, v in page.items()) or recorded["shape"] != [1031, 128]:
            raise ValueError("Page provenance mismatch")
        path = (manifest_path.parent / page["image_path"]).resolve()
        if not path.is_relative_to(manifest_path.parent) or hashlib.sha256(path.read_bytes()).hexdigest() != page["image_sha256"]:
            raise ValueError("Page render mismatch")
        tensor = valid_embedding(tensor, rows=1031)
        if tensor.dtype != torch.bfloat16:
            raise ValueError("Expected original BF16 cache")
        vector = tensor.float()
        data = json.dumps(vector.tolist(), separators=(",", ":"), allow_nan=False).encode()
        prepared.append((page, data, hashlib.sha256(vector.numpy().tobytes()).hexdigest()))
    output.mkdir(parents=True)
    entries = []
    for i, (page, data, tensor_hash) in enumerate(prepared):
        filename = f"page-{i:03}.json"
        (output / filename).write_bytes(data)
        entries.append({"source_page_id": page["page_id"], "render_sha256": page["image_sha256"],
                        "file": filename, "json_sha256": hashlib.sha256(data).hexdigest(),
                        "embedding_sha256": tensor_hash, "token_count": 1031})
    result = {"schema": "verified-search-features-v1", "source": config, "pages": entries}
    (output / "manifest.json").write_text(json.dumps(result, indent=2)+'\n', encoding="utf-8")
    print(json.dumps({"prepared_pages": len(entries), "tokens_per_page": 1031, "dimension": 128,
                      "feature_file_sha256": config["files"]["page_embeddings.pt"], "gpu_used": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args().output)
