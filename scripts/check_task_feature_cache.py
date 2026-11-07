"""R19 CPU-only full feature verification, including cancelled-attempt cost."""
import hashlib
import json
from pathlib import Path
import sqlite3


def main():
    import torch
    root = Path(__file__).resolve().parents[1]
    ui = root / "runtime/verification/r19/ui"
    output = root / "docs/checks/stage2-3c-features.json"
    if output.exists():
        raise RuntimeError("Evidence already exists")
    audits = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ui / "pages").glob("*.json"))]
    tensors = []
    for row in audits:
        path = root / row["tensor_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["tensor_sha256"]
        saved = torch.load(path, map_location="cpu", weights_only=True)
        tensor = saved["embeddings"]
        assert tensor.shape == (1031, 128) and tensor.dtype == torch.bfloat16 and torch.isfinite(tensor).all()
        assert saved["schema"] == "full-page-features-v1" and saved["visual_patch_count"] == 1024
        assert saved["encoder_sha256"] == row["profile_sha256"] and row["network_attempts"] == 0
        exported = torch.tensor(json.loads((root / row["export_path"]).read_text()), dtype=torch.float32)
        assert torch.equal(tensor.float(), exported)
        tensors.append({"path": row["tensor_path"], "shape": list(tensor.shape), "dtype": str(tensor.dtype), "patches": saved["visual_patch_count"]})
    with sqlite3.connect(ui / "metadata.sqlite3") as db:
        active = {r[0] for r in db.execute("SELECT tensor_path FROM page_features")}
    assert len(tensors) == 16 and len(active) == 11
    assert active <= {r["path"] for r in tensors}
    output.write_text(json.dumps({"date": "2026-11-08", "round": "R19", "stage": "2-3C", "overall": "passed", "actual_page_forwards": len(tensors), "activated_full_features": len(active), "cancelled_attempt_page_forwards": len(tensors) - len(active), "worker_pids": sorted({r["worker_pid"] for r in audits}), "tensors": tensors, "limits": ["CPU cache identity/shape/finite/export verification; no official scoring or accuracy rerun", "Five forwards belong to cancelled attempt and remain counted as cost"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("R19 CPU:16 complete BF16 tensors,11 activated +5 cancelled; all1031x128/1024 patches, float32 exports identical")


if __name__ == "__main__":
    main()
