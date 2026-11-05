"""Offline real encoding -> exact MaxSim -> Top-k, over every page of two PDFs.

No server, Qdrant, gold annotations or old prediction reader is involved. Each run
re-encodes all page images and all supplied queries and produces an audit report.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    cache = Path.home() / ".cache/huggingface/hub"
    parser.add_argument("--adapter", type=Path, default=cache / "models--vidore--colpali/snapshots/7754422bfa37f8e3cd771e13d4d7f07de3103c95")
    parser.add_argument("--base", type=Path, default=cache / "models--vidore--colpaligemma-3b-mix-448-base/snapshots/6ff0d944ea09c3ead97d2bc57427e3d4f01d192f")
    parser.add_argument("--profile", type=Path, default=ROOT / "configs/colpali_local.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "runtime/corpus/manifest.json")
    parser.add_argument("--queries-file", type=Path)
    parser.add_argument("--question", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=["cuda:0", "cpu"], default="cuda:0")
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "runtime") or output.exists():
        parser.error("Output must be a NEW directory inside runtime/")
    output.mkdir(parents=True)
    report = {"schema": "colpali-live-verification-v1", "status": "running",
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "stage": "initializing", "device": args.device, "network_attempts": [],
              "page_cache_read": False, "prediction_table_read": False, "training": False,
              "errors": [], "queries": [], "page_encoding": []}

    def save() -> None:
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                       allow_nan=False), encoding="utf-8")

    def deny_network(event, audit_args) -> None:
        if event in {"socket.connect", "socket.getaddrinfo"}:
            report["network_attempts"].append(event)
            raise RuntimeError(f"Network disabled for verification: {event}")

    # Set before third-party imports; new process for each run.
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        os.environ[name] = "1"
    os.environ["COLPALI_SCORES_BACKEND"] = "torch"
    temp = ROOT / "runtime/tmp"
    temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(temp)
    sys.addaudithook(deny_network)
    started = time.perf_counter()
    save()
    try:
        import torch
        import pymupdf
        from backend.algorithms.colpali_adapter import ColPaliAdapter, file_sha256
        from backend.algorithms.contracts import maxsim_scores, top_k

        torch.set_num_threads(4)
        torch.manual_seed(0)
        questions = list(args.question)
        if args.queries_file:
            questions.extend(json.loads(args.queries_file.read_text("utf-8"))["questions"])
        if not questions:
            raise ValueError("Supply --question or --queries-file; no preset prediction replay")
        if not 1 <= args.k <= 50:
            raise ValueError("k must be between 1 and 50")
        corpus = json.loads(args.corpus.read_text("utf-8"))
        pages = corpus["pages"]
        if len({p["page_id"] for p in pages}) != len(pages):
            raise ValueError("Duplicate page identity")
        for doc in corpus["documents"]:
            path = (args.corpus.parent / doc["pdf_path"]).resolve(strict=True)
            if not path.is_relative_to(args.corpus.parent.resolve()) or file_sha256(path) != doc["sha256"]:
                raise ValueError("PDF identity mismatch")
            with pymupdf.open(path) as pdf:
                indexes = sorted(p["page_index"] for p in pages if p["document_id"] == doc["document_id"])
                if len(pdf) != doc["page_count"] or indexes != list(range(len(pdf))):
                    raise ValueError("Corpus is missing or duplicating PDF pages")
        known_docs = {d["document_id"] for d in corpus["documents"]}
        if any(p["document_id"] not in known_docs or p["page_number"] != p["page_index"] + 1 for p in pages):
            raise ValueError("Invalid page/document mapping")
        report.update(corpus_sha256=file_sha256(args.corpus), page_count=len(pages),
                      document_count=len(corpus["documents"]), documents=corpus["documents"],
                      python=sys.version, executable=sys.executable,
                      packages={d.metadata["Name"]: d.version for d in metadata.distributions()},
                      old_research_import=False)
        if any(str(ROOT.parent / "layoutpatch") + os.sep in p for p in sys.path):
            raise RuntimeError("Research repository unexpectedly present on sys.path")
        if args.device.startswith("cuda"):
            torch.cuda.reset_peak_memory_stats()
            free, total = torch.cuda.mem_get_info()
            report["gpu"] = {"name": torch.cuda.get_device_name(), "initial_free_bytes": free,
                             "total_bytes": total, "cuda_build": torch.version.cuda}
        report["stage"] = "model_load"
        save()
        adapter = ColPaliAdapter(args.adapter, args.base, args.profile, args.device)
        adapter.load()
        report.update(profile_id=adapter.profile_id, profile=adapter.profile,
                      model_files_verified=adapter.verified_files, loading_info=adapter.loading_info,
                      load_seconds=adapter.load_seconds,
                      model_parameters=sum(p.numel() for p in adapter.model.parameters()),
                      trainable_parameters=sum(p.numel() for p in adapter.model.parameters() if p.requires_grad))
        print(f"Model loaded in {adapter.load_seconds:.2f}s", flush=True)
        report["stage"] = "page_encoding"
        embeddings = []
        for page in pages:
            path = (args.corpus.parent / page["image_path"]).resolve(strict=True)
            if not path.is_relative_to(args.corpus.parent.resolve()) or file_sha256(path) != page["image_sha256"]:
                raise ValueError("Page image identity mismatch")
            tick = time.perf_counter()
            embedding = adapter.encode_page(path)
            embeddings.append(embedding)
            report["page_encoding"].append({**page, "shape": list(embedding.shape),
                                             "seconds": time.perf_counter() - tick})
            save()
            print(f"Encoded {page['page_id']} {tuple(embedding.shape)}", flush=True)
        torch.save({"profile_id": adapter.profile_id, "page_ids": [p["page_id"] for p in pages],
                    "embeddings": embeddings}, output / "page_embeddings.pt")
        report["stage"] = "query_encoding_and_search"
        query_embeddings = []
        for offset in range(0, len(questions), 2):
            tick = time.perf_counter()
            query_embeddings.extend(adapter.encode_queries(questions[offset:offset + 2]))
            report.setdefault("query_batch_seconds", []).append(time.perf_counter() - tick)
        page_lookup = {p["page_id"]: p for p in pages}
        page_ids = list(page_lookup)
        for question, query in zip(questions, query_embeddings, strict=True):
            tick = time.perf_counter()
            scores = maxsim_scores(query, embeddings)
            search_seconds = time.perf_counter() - tick
            # Independent library reference using the SAME float32 vectors, no GPU TF32.
            reference = adapter.processor.score_multi_vector([query.float()],
                        [p.float() for p in embeddings], batch_size=16, device="cpu")[0]
            delta = float((scores - reference).abs().max())
            if not torch.allclose(scores, reference, atol=1e-5, rtol=1e-5):
                raise ValueError(f"Adapter and processor scoring disagree: max delta {delta}")
            hits = top_k(page_ids, scores, args.k)
            reference_hits = top_k(page_ids, reference, args.k)
            if [h.page_id for h in hits] != [h.page_id for h in reference_hits]:
                raise ValueError("Adapter and reference Top-k disagree")
            report["queries"].append({"question": question, "token_shape": list(query.shape),
                "query_embedding_sha256": hashlib.sha256(query.view(torch.uint8).numpy().tobytes()).hexdigest(),
                "search_seconds": search_seconds, "reference_max_abs_diff": delta,
                "reference_top_k_matches": True,
                "top_k": [{**asdict(hit), "document_id": page_lookup[hit.page_id]["document_id"],
                           "page_number": page_lookup[hit.page_id]["page_number"]} for hit in hits]})
            print(json.dumps(report["queries"][-1], ensure_ascii=False), flush=True)
        torch.save({"questions": questions, "profile_id": adapter.profile_id,
                    "embeddings": query_embeddings}, output / "query_embeddings.pt")
        report.update(query_token_audit=adapter.query_audit, page_forward_calls=adapter.page_calls,
                      query_forward_calls=adapter.query_calls,
                      feature_bytes=(output / "page_embeddings.pt").stat().st_size,
                      query_feature_bytes=(output / "query_embeddings.pt").stat().st_size)
        if args.device.startswith("cuda"):
            report["gpu"].update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                                 peak_reserved_bytes=torch.cuda.max_memory_reserved())
        if report["network_attempts"]:
            raise RuntimeError("Unexpected network attempt during offline verification")
        report.update(status="passed", stage="complete", total_seconds=time.perf_counter() - started,
                      completed_utc=datetime.now(timezone.utc).isoformat())
        save()
        print(f"PASSED: {output / 'report.json'}", flush=True)
        return 0
    except Exception as error:
        report.update(status="failed", total_seconds=time.perf_counter() - started)
        report["errors"].append({"type": type(error).__name__, "message": str(error)})
        save()
        (output / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
