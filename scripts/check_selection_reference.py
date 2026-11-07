"""R16 official CPU reference using same-run query vectors and complete reused page tensors."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(input_path, output_path):
    if output_path.exists():
        raise RuntimeError("Reference output exists; use a new evidence path")
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from colpali_engine.models import ColPaliProcessor
    from backend.algorithms.contracts import maxsim_scores
    torch.set_num_threads(4)
    old = torch.load(ROOT / "runtime/verification/20261105-gpu-first/page_embeddings.pt", map_location="cpu", weights_only=True)
    original = dict(zip(old["page_ids"], old["embeddings"], strict=True))
    cases = json.loads(input_path.read_text(encoding="utf-8"))
    reports, tensors_checked = [], {}
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
                    raise AssertionError("Incomplete full-page feature")
                tensors_checked[page_id] = {"shape": list(tensor.shape), "dtype": str(tensor.dtype), "visual_patch_count": 1024}
            else:
                tensor = original[spec["source_page_id"]]
            tensors.append(tensor)
        direct = maxsim_scores(query, tensors)
        official = ColPaliProcessor.score_multi_vector([query], [p.float() for p in tensors], batch_size=16, device="cpu")[0]
        if not torch.allclose(direct, official, atol=1e-4, rtol=1e-5):
            raise AssertionError("Direct/official mismatch")
        scores = {key: float(value) for key, value in zip(ids, official, strict=True)}
        ordered = sorted(ids, key=lambda key: (-scores[key], key))
        hits = case["items"]
        if len(hits) != min(case["k"], len(ids)):
            raise AssertionError("Selected result count mismatch")
        deltas = [abs(hit["page_score"] - scores[hit["page_id"]]) for hit in hits]
        if any(delta > 1e-4 + 1e-5 * abs(scores[hit["page_id"]]) for hit, delta in zip(hits, deltas, strict=True)):
            raise AssertionError("Qdrant/official mismatch")
        if any(abs(hit["page_score"] - scores[key]) > 1e-4 + 1e-5 * abs(scores[key]) for hit, key in zip(hits, ordered[:len(hits)], strict=True)):
            raise AssertionError("Selected Top-k mismatch")
        non_tied = all(abs(scores[a]-scores[b]) > 1e-4 + 1e-5 * abs(scores[a]) for a,b in zip(ordered, ordered[1:]))
        if non_tied and [hit["page_id"] for hit in hits] != ordered[:len(hits)]:
            raise AssertionError("Non-tied ranking mismatch")
        reports.append({"name": case["name"], "target_document_id": case["target_document_id"], "authorized_pages": len(ids),
                        "returned": len(hits), "max_abs_diff": max(deltas, default=0), "top_k_matches": True, "non_tied": non_tied,
                        "query_valid_tokens": len(query), "valid_pad_id_tokens": audit["valid_pad_id_tokens"]})
    report = {"date": "2026-11-07", "round": "R16", "stage": "2-3A", "status": "passed", "atol": 1e-4, "rtol": 1e-5,
              "cases": reports, "full_tensors_checked": tensors_checked,
              "reference": "official ColPaliProcessor and CPU float32 MaxSim; same-run HTTP query vectors; each exact selected/library scope",
              "page_encodings": 0, "limits": ["six development cases, not accuracy evaluation; original full tensors reused read-only"]}
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"R16 official reference: {len(reports)} cases, unchanged tolerance, exact scoped Top-k passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    main(args.input, args.output)
