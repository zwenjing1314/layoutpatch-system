"""No in-place rebuilds. Remote work is outside the SQLite writer transaction."""
from copy import deepcopy
import json
import os
import subprocess
import time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT
from backend.db.models import (Document, DocumentVersion, IndexEvent, IndexGeneration, IndexOperation,
    IndexPage, Page, PipelineProfile, SystemState, new_id, now)
from backend.db.seed import canonical, sha
from backend.documents.lifecycle import producing
from backend.documents.pipeline import write_transaction
from backend.search.indexing import feature_digest
from backend.search.qdrant import SearchUnavailable, validate_vector
from backend.search.scope import active_index, index_epoch, profile_identity


def verify_encoder(expected):
    result = subprocess.run([str(ROOT / ".venv/Scripts/python.exe"), "-B", "-m", "scripts.verify_encoder_identity"],
        cwd=ROOT, capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env={**os.environ, "PYTHONUTF8": "1"})
    try:
        value = json.loads(result.stdout)
        if (result.returncode or value["encoder_sha256"] != expected or value["verified_files"] != 13
            or value["implementation_count"] != 2 or value["network_attempts"] != 0 or value["inference_count"] != 0):
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise SearchUnavailable("Encoder identity mismatch") from None
    return value


def fail(code="INDEX_STATE_CHANGED", status=409):
    raise HTTPException(status, code)


def event(db, operation, outcome, code, clock):
    db.add(IndexEvent(actor_id=operation.actor_id, operation_id=operation.id, action=operation.kind,
        outcome=outcome, code=code, occurred_at=clock()))


def capture(db, target_id, *, pending_profile=False):
    current, _ = active_index(db)
    target = db.get(IndexGeneration, target_id)
    profile = db.get(PipelineProfile, target.profile_id) if target else None
    if target is None or target.status != "ready" or not profile:
        fail("INDEX_NOT_READY")
    if profile.status != "validated" and not pending_profile:
        fail("PROFILE_NOT_VALIDATED")
    encoder = profile_identity(profile)
    if not target.feature_file_sha256 or not target.source_manifest_sha256:
        fail("INDEX_IDENTITY_MISSING")
    # All current ready versions, including disabled owners' private documents.
    # No document names, paths, questions or arbitrary config enter the API/event projection.
    docs = list(db.execute(select(Document.id, Document.owner_id, Document.active_version_id, Document.access_version,
        DocumentVersion.page_count).join(DocumentVersion, DocumentVersion.id == Document.active_version_id)
        .where(Document.status == "ready", Document.deleted_at.is_(None), DocumentVersion.document_id == Document.id)
        .order_by(Document.id)))
    if db.scalar(select(Document.id).where(Document.status == "ready", Document.deleted_at.is_(None),
        Document.active_version_id.is_(None)).limit(1)):
        fail("CORPUS_INCOMPLETE")
    required = {}
    for doc_id, owner_id, version_id, access_version, count in docs:
        pages = list(db.scalars(select(Page).where(Page.document_version_id == version_id).order_by(Page.page_index)))
        if [p.page_index for p in pages] != list(range(count)):
            fail("CORPUS_INCOMPLETE")
        required.update({p.id: {"document_id": doc_id, "document_version_id": version_id,
            "owner_id": owner_id, "render_sha256": p.render_sha256} for p in pages})
    members = {}
    for ip, page, version in db.execute(select(IndexPage, Page, DocumentVersion)
        .join(Page, Page.id == IndexPage.page_id).join(DocumentVersion, DocumentVersion.id == Page.document_version_id)
        .where(IndexPage.index_id == target.id).order_by(IndexPage.page_id)):
        members[page.id] = {"embedding_sha256": ip.embedding_sha256, "document_id": version.document_id,
            "document_version_id": version.id, "render_sha256": page.render_sha256}
    if (not set(required).issubset(members) or len(members) != target.page_count or target.vector_count != len(members)*1031):
        fail("INDEX_COVERAGE_MISMATCH")
    value = {"active": current.id, "epoch": index_epoch(db), "target": target.id, "profile_id": profile.id,
        "config_sha256": profile.config_sha256, "encoder_sha256": encoder, "collection": target.collection_name,
        "feature_sha256": target.feature_file_sha256, "manifest_sha256": target.source_manifest_sha256,
        "docs": [tuple(d) for d in docs], "required": required, "members": members}
    return value, sha(canonical(value).encode())


def remote(qdrant, snap, checkpoint):
    checkpoint()
    qdrant.check_info(qdrant.info(snap["collection"]), len(snap["members"]))
    points = qdrant.all_points(snap["collection"])
    lookup = {str(p["id"]): p for p in points}
    if len(points) != len(lookup) or set(lookup) != set(snap["members"]):
        fail("INDEX_REMOTE_MISMATCH", 503)
    for page_id, point in lookup.items():
        checkpoint()
        payload = point.get("payload", {})
        if (payload.get("page_id") != page_id or payload.get("index_generation") != snap["target"]
            or payload.get("profile_id") != snap["profile_id"] or any(payload.get(k) != v for k, v in snap["members"][page_id].items())
            or set(point.get("vector", {})) != {"original"}
            or feature_digest(validate_vector(point["vector"]["original"], rows=1031)) != payload.get("embedding_sha256")):
            fail("INDEX_REMOTE_MISMATCH", 503)
    return lookup


def operation_view(row):
    return {"operation_id": row.id, "kind": row.kind, "status": row.status, "source_id": row.source_id,
        "target_id": row.target_id, "expected_epoch": row.expected_epoch, "error_code": row.error_code,
        "metrics": json.loads(row.metrics_json), "created_at": row.created_at, "updated_at": row.updated_at}


def manage(engine, qdrant, kind, body, authorize, clock=time.time, verifier=None):
    """Durable reservation; explicit retry gets a new ID after reviewing terminal failure.

    A disconnect never launches an automatic retry. Completed identical requests replay
    their original outcome, even when the active pointer subsequently changes.
    """
    started = time.monotonic()
    verifier = verifier or verify_encoder
    request_hash = sha(canonical({"kind": kind, **body.model_dump(mode="json", exclude={"request_id"})}).encode())
    with producing(engine):
        with write_transaction(engine) as db:
            actor = authorize(db)
            existing = db.scalar(select(IndexOperation).where(IndexOperation.actor_id == actor,
                IndexOperation.request_id == str(body.request_id)))
            if existing:
                if existing.input_sha256 != request_hash:
                    fail("INDEX_REQUEST_CONFLICT")
                return operation_view(existing)
            if db.scalar(select(IndexOperation.id).where(IndexOperation.status == "running").limit(1)):
                fail("INDEX_OPERATION_BUSY")
            snap, stamp = capture(db, str(body.index_id), pending_profile=kind == "verify")
            if snap["active"] != str(body.active_index_id) or snap["epoch"] != body.index_epoch:
                fail()
            if kind == "rebuild" and snap["target"] != snap["active"]:
                fail("REBUILD_REQUIRES_ACTIVE_INDEX")
            state = db.get(SystemState, 1)
            if state is None:
                # Legacy imports select their sole ready generation implicitly.
                # Pin it before another ready candidate can make that ambiguous.
                db.add(SystemState(id=1, active_index_id=snap["active"], index_epoch=snap["epoch"]))
            elif state.active_index_id is None:
                state.active_index_id = snap["active"]
            candidate_id = new_id() if kind == "rebuild" else snap["target"]
            if kind == "rebuild":
                db.add(IndexGeneration(id=candidate_id, profile_id=snap["profile_id"],
                    collection_name="layoutpatch_system_rebuild_" + candidate_id.replace("-", ""), status="building"))
                db.flush()
            row = IndexOperation(actor_id=actor, request_id=str(body.request_id), input_sha256=request_hash,
                kind=kind, source_id=snap["active"], target_id=candidate_id, expected_epoch=snap["epoch"], status="running")
            db.add(row); db.flush(); operation_id = row.id
            event(db, row, "started", "OK", clock)
        metrics = {}
        def checkpoint():
            if time.monotonic() - started > 600:
                fail("INDEX_DEADLINE_EXCEEDED", 503)
        try:
            # File/implementation identity is verified afresh for every management write.
            metrics.update(verifier(snap["encoder_sha256"]))
            points = remote(qdrant, snap, checkpoint)
            target_collection = None
            if kind == "rebuild":
                target_collection = "layoutpatch_system_rebuild_" + candidate_id.replace("-", "")
                if qdrant.info(target_collection) is not None:
                    fail("CANDIDATE_EXISTS", 503)
                qdrant.create(target_collection)
                rebuilt = []
                for page_id in sorted(snap["required"]):
                    checkpoint()
                    point = deepcopy(points[page_id])
                    # Visibility/ownership in an index payload never grants access.
                    point["payload"] = {**point["payload"], "index_generation": candidate_id}
                    qdrant.upsert(target_collection, [point]); rebuilt.append(point)
                candidate_snap = {**snap, "target": candidate_id, "collection": target_collection,
                    "members": {p: snap["members"][p] for p in snap["required"]}}
                remote(qdrant, candidate_snap, checkpoint)
            checkpoint()
            count = len(snap["required"] if kind == "rebuild" else snap["members"])
            metrics.update(elapsed_ms=round((time.monotonic()-started)*1000, 3), page_count=count,
                vector_count=count*1031, full_bf16_bytes=count*1031*128*2,
                vector_float32_bytes=count*1031*128*4, page_encoding_count=0,
                storage_basis="logical_vectors_excludes_files_payload_and_engine_overhead")
            with write_transaction(engine) as db:
                if authorize(db) != actor:
                    fail("INDEX_AUTHORITY_CHANGED", 403)
                _, current_stamp = capture(db, str(body.index_id), pending_profile=kind == "verify")
                if current_stamp != stamp:
                    fail()
                row = db.get(IndexOperation, operation_id)
                if row.status != "running":
                    fail()
                if kind == "rebuild":
                    candidate = db.get(IndexGeneration, candidate_id)
                    for page_id in sorted(snap["required"]):
                        db.add(IndexPage(index_id=candidate_id, page_id=page_id,
                            embedding_sha256=snap["members"][page_id]["embedding_sha256"], token_count=1031))
                    candidate.status, candidate.page_count, candidate.vector_count = "ready", count, count*1031
                    candidate.feature_file_sha256 = sha(canonical({"parent": snap["feature_sha256"],
                        "members": candidate_snap["members"]}).encode())
                    candidate.source_manifest_sha256 = sha(canonical({"schema": "full-vector-rebuild-v1", "parent": snap["target"],
                        "profile": snap["config_sha256"], "source": snap["manifest_sha256"], "members": candidate_snap["members"]}).encode())
                if kind == "verify":
                    db.get(PipelineProfile, snap["profile_id"]).status = "validated"
                if kind == "activate" and snap["target"] != snap["active"]:
                    state = db.get(SystemState, 1)
                    if state is None:
                        db.add(SystemState(id=1, active_index_id=snap["target"], index_epoch=snap["epoch"]+1))
                    else:
                        state.active_index_id, state.index_epoch = snap["target"], snap["epoch"]+1
                row.status, row.metrics_json, row.updated_at = "completed", canonical(metrics), now()
                event(db, row, "success", "OK", clock)
                db.flush(); result = operation_view(row)
            return result
        except Exception as exc:
            code = exc.detail if isinstance(exc, HTTPException) else "INDEX_VERIFICATION_FAILED"
            # Do not demote an active/old ready index on failure, even for remote errors.
            with write_transaction(engine) as db:
                row = db.get(IndexOperation, operation_id)
                row.status, row.error_code, row.updated_at = "failed", code, now()
                metrics["elapsed_ms"] = round((time.monotonic()-started)*1000, 3)
                row.metrics_json = canonical(metrics)
                if kind == "rebuild":
                    db.get(IndexGeneration, candidate_id).status = "failed"
                event(db, row, "failed", code, clock)
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(503, "INDEX_VERIFICATION_FAILED") from None


def recover(engine):
    with write_transaction(engine) as db:
        for row in db.scalars(select(IndexOperation).where(IndexOperation.status == "running")):
            row.status, row.error_code, row.updated_at = "interrupted", "INDEX_OPERATION_INTERRUPTED", now()
            if row.kind == "rebuild":
                candidate = db.get(IndexGeneration, row.target_id)
                if candidate and candidate.status == "building":
                    candidate.status = "failed"
            event(db, row, "failed", "INDEX_OPERATION_INTERRUPTED", time.time)
