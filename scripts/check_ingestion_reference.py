"""R15 same-run query vectors against complete authorized old/new page tensors."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(input_path, output_path):
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from colpali_engine.models import ColPaliProcessor
    from backend.algorithms.contracts import maxsim_scores
    torch.set_num_threads(4)
    old = torch.load(ROOT / "runtime/verification/20261105-gpu-first/page_embeddings.pt", map_location="cpu", weights_only=True)
    original = dict(zip(old["page_ids"], old["embeddings"], strict=True))
    cases = json.loads(input_path.read_text(encoding="utf-8"))
    reports = []
    tensor_checks = {}
    for case in cases:
        audit = json.loads(Path(case["audit"]).read_text(encoding="utf-8"))
        query = torch.tensor(audit["vector"], dtype=torch.float32)
        ids, tensors = [], []
        for page_id, spec in case["pages"].items():
            ids.append(page_id)
            if "tensor_path" in spec:
                saved = torch.load(ROOT / spec["tensor_path"], map_location="cpu", weights_only=True)
                tensor = saved["embeddings"]
                if tensor.shape != (1031, 128) or tensor.dtype != torch.bfloat16 or saved["visual_patch_count"] != 1024:
                    raise AssertionError("Complete BF16 feature contract mismatch")
                tensor_checks[page_id] = {"shape": list(tensor.shape), "dtype": str(tensor.dtype), "visual_patch_count": 1024}
            else:
                tensor = original[spec["source_page_id"]]
            tensors.append(tensor)
        direct = maxsim_scores(query, tensors)
        official = ColPaliProcessor.score_multi_vector([query], [p.float() for p in tensors], batch_size=16, device="cpu")[0]
        if not torch.allclose(direct, official, atol=1e-4, rtol=1e-5):
            raise AssertionError("CPU/reference disagreement")
        scores = {i: float(v) for i, v in zip(ids, official, strict=True)}
        ordered = sorted(ids, key=lambda i: (-scores[i], i))
        hits = case["items"]
        if len(hits) != min(case["k"], len(ids)):
            raise AssertionError("Incomplete filtered hit list")
        deltas = [abs(h["page_score"] - scores[h["page_id"]]) for h in hits]
        for h, delta in zip(hits, deltas):
            if delta > 1e-4 + 1e-5 * abs(scores[h["page_id"]]):
                raise AssertionError("Qdrant score differs from official reference")
        returned = [scores[h["page_id"]] for h in hits]
        if any(abs(a-b) > 1e-4+1e-5*abs(b) for a, b in zip(returned, [scores[i] for i in ordered[:len(hits)]], strict=True)):
            raise AssertionError("Filtered Top-k mismatch")
        strict = all(abs(scores[a]-scores[b]) > 1e-4+1e-5*abs(scores[a]) for a,b in zip(ordered, ordered[1:]))
        if strict and [h["page_id"] for h in hits] != ordered[:len(hits)]:
            raise AssertionError("Non-tied rank mismatch")
        reports.append({"name": case["name"], "authorized_pages": len(ids), "returned": len(hits),
                        "max_abs_diff": max(deltas, default=0), "top_k_matches": True, "non_tied": strict,
                        "query_valid_tokens": len(query), "valid_pad_id_tokens": audit["valid_pad_id_tokens"]})
    output_path.write_text(json.dumps({"date": "2026-11-07", "round": "R15", "stage": "2-2", "status": "passed",
        "atol": 1e-4, "rtol": 1e-5, "cases": reports, "new_full_tensors": tensor_checks,
        "reference": "official ColPaliProcessor plus CPU float32 MaxSim; actual same-run HTTP query vectors"}, indent=2) + "\n", encoding="utf-8")
    print(f"Official reference: {len(reports)} cases, {len(tensor_checks)} new complete BF16 pages passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.input, args.output)
