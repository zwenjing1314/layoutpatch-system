"""Single persistent-job dispatcher, immutable candidate collections, atomic activation."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import os
import time

from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.db.connection import ROOT
from backend.db.models import Document, DocumentVersion, IndexGeneration, IndexPage, Job, Page, PageFeature, SystemState, User, new_id, now
from backend.db.seed import canonical, sha
from backend.search.indexing import feature_digest
from backend.search.qdrant import SearchUnavailable, validate_vector
from backend.search.scope import active_index, index_epoch
from backend.search.worker import SearchBusy
from backend.documents.task_state import sync_attempt
from backend.documents.lifecycle import producing


class IngestError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def write_transaction(engine):
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with Session(bind=connection, expire_on_commit=False) as db:
                yield db
                db.flush()
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def private_file(relative, base=ROOT / "runtime"):
    path = (ROOT / relative).resolve(strict=True)
    if not path.is_relative_to(base.resolve()):
        raise IngestError("INGEST_PATH_INVALID")
    return path


def render_pdf(worker, version, output):
    # Native parser gets a finite subprocess lifetime; never import GPU in Web.
    source = private_file(version.pdf_path)
    result = subprocess.run([str(worker.settings.model_python), "-B", str(ROOT / "scripts/render_upload.py"),
                             str(source), str(output), version.pdf_sha256, str(version.page_count)],
                            cwd=ROOT, capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode != 0:
        raise IngestError("RENDER_FAILED")
    return json.loads((output / "render-manifest.json").read_text(encoding="utf-8"))


class IngestionRunner:
    def __init__(self, engine, worker, qdrant, renderer=render_pdf, max_seconds=None):
        self.engine, self.worker, self.qdrant, self.renderer = engine, worker, qdrant, renderer
        self.stop_event = threading.Event()
        self.thread = None
        self.max_seconds = float(max_seconds if max_seconds is not None else os.getenv("LAYOUTPATCH_INGEST_MAX_SECONDS", "900"))
        if not 1 <= self.max_seconds <= 7200:
            raise ValueError("Ingestion deadline must be between1 and7200 seconds")

    def start(self):
        self.thread = threading.Thread(target=self.loop, name="private-pdf-ingestion", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=200)
            if self.thread.is_alive():
                raise RuntimeError("Ingestion worker did not stop within its bounded operation")

    def loop(self):
        while not self.stop_event.is_set():
            try:
                if self.run_one():
                    continue
            except Exception:
                # No input/path/vector/credentials in logs. Failed connection is retried;
                # an already claimed task is recovered to interrupted on restart.
                pass
            self.stop_event.wait(1)

    def checkpoint(self, job_id, stage=None, progress=None, *, attempt=None, deadline=None):
        with write_transaction(self.engine) as db:
            job = db.get(Job, job_id)
            if job and job.cancel_requested_at and (attempt is None or job.attempt == attempt):
                raise IngestError("CANCELLED_BY_OWNER")
            if self.stop_event.is_set():
                raise IngestError("INGEST_INTERRUPTED")
            if deadline is not None and time.monotonic() >= deadline:
                raise IngestError("INGEST_DEADLINE_EXCEEDED")
            user = db.get(User, job.owner_id) if job else None
            version = db.get(DocumentVersion, job.document_version_id) if job else None
            doc = db.get(Document, version.document_id) if version else None
            if (not job or job.status != "running" or attempt is not None and job.attempt != attempt or not user or not user.active or not doc
                    or doc.owner_id != job.owner_id or doc.deleted_at or doc.status != "registered"
                    or doc.active_version_id is not None):
                raise IngestError("INGEST_AUTHORITY_CHANGED")
            if stage:
                job.stage = stage
            if progress is not None:
                job.progress = progress
            job.updated_at = now()
            sync_attempt(db, job)

    def run_one(self):
        with producing(self.engine):
            return self._run_one()

    def _run_one(self):
        with write_transaction(self.engine) as db:
            job = db.scalar(select(Job).where(Job.status == "queued").order_by(Job.created_at, Job.id).limit(1))
            if job is None:
                return False
            job.status, job.stage, job.updated_at = "running", "rendering", now()
            job_id, attempt = job.id, job.attempt
            sync_attempt(db, job)
        deadline = time.monotonic() + self.max_seconds
        def checkpoint(stage=None, progress=None):
            self.checkpoint(job_id, stage, progress, attempt=attempt, deadline=deadline)
        candidate_id = None
        phase = "preparing"
        try:
            checkpoint()
            with Session(self.engine, expire_on_commit=False) as db:
                job = db.get(Job, job_id)
                version = db.get(DocumentVersion, job.document_version_id)
                doc = db.get(Document, version.document_id)
                old, profile = active_index(db)
                old_id, profile_id = old.id, profile.id
                old_epoch = index_epoch(db)
                encoder_sha = sha((ROOT / "configs/colpali_local.json").read_bytes())
                config = json.loads(profile.config_json)
                if (sha(profile.config_json.encode()) != profile.config_sha256 or config["encoder"] != json.loads((ROOT / "configs/colpali_local.json").read_text())
                        or config["qdrant_design"] != {"vector_name": "original", "dimension": 128, "distance": "Dot", "multivector": "MAX_SIM", "exact": True}
                        or any(config["render"].get(k) != v for k, v in {"dpi": 144, "colorspace": "RGB", "format": "PNG"}.items())):
                    raise IngestError("INGEST_PROFILE_CHANGED")
                memberships = {r.page_id: r.embedding_sha256 for r in db.scalars(select(IndexPage).where(IndexPage.index_id == old.id))}
                old_identities = {}
                for page in db.scalars(select(Page).where(Page.id.in_(memberships))):
                    old_version = db.get(DocumentVersion, page.document_version_id)
                    old_identities[page.id] = {"document_id": old_version.document_id, "document_version_id": old_version.id,
                                               "render_sha256": page.render_sha256}
                if len(memberships) != old.page_count or old.vector_count != old.page_count * 1031:
                    raise IngestError("ACTIVE_INDEX_INCOMPLETE")
            output = ROOT / "runtime/corpus/ingest" / job_id / f"attempt-{job.attempt}"
            phase = "rendering"
            manifest = self.renderer(self.worker, version, output)
            checkpoint()
            entries = manifest["pages"]
            if (manifest["pdf_sha256"] != version.pdf_sha256 or len(entries) != version.page_count
                    or [p["page_index"] for p in entries] != list(range(version.page_count))):
                raise IngestError("RENDER_IDENTITY_MISMATCH")
            render_json = canonical(manifest["render_profile"])
            if any(manifest["render_profile"].get(k) != v for k, v in {"dpi": 144, "colorspace": "RGB", "format": "PNG"}.items()):
                raise IngestError("RENDER_PROFILE_MISMATCH")
            features, points = [], []
            candidate_id = new_id()
            phase = "encoding"
            for number, entry in enumerate(entries):
                checkpoint("encoding", 5 + int(70 * number / len(entries)))
                image_path = private_file(entry["image_path"], ROOT / "runtime/corpus/ingest")
                if sha(image_path.read_bytes()) != entry["render_sha256"] or image_path.stat().st_size > 20 * 1024 * 1024:
                    raise IngestError("RENDER_IDENTITY_MISMATCH")
                with Image.open(image_path) as image:
                    if image.format != "PNG" or image.mode != "RGB" or image.size != (entry["width_px"], entry["height_px"]):
                        raise IngestError("RENDER_IDENTITY_MISMATCH")
                    image.verify()
                page_id = new_id()
                encoded = self.worker.encode_page(image_path, output / f"features-{number:04}", entry["render_sha256"], encoder_sha)
                if (encoded.get("profile_sha256") != encoder_sha or encoded.get("network_attempts") != 0
                        or encoded.get("token_count") != 1031 or encoded.get("dimension") != 128 or encoded.get("patch_tokens") != 1024):
                    raise IngestError("FEATURE_IDENTITY_MISMATCH")
                tensor = private_file(encoded["tensor_path"], output)
                export = private_file(encoded["export_path"], output)
                if sha(tensor.read_bytes()) != encoded["tensor_sha256"] or sha(export.read_bytes()) != encoded["export_sha256"]:
                    raise IngestError("FEATURE_IDENTITY_MISMATCH")
                vector = validate_vector(json.loads(export.read_text()), rows=1031)
                if encoded["embedding_sha256"] != feature_digest(vector):
                    raise IngestError("FEATURE_IDENTITY_MISMATCH")
                features.append((page_id, entry, encoded))
                points.append({"id": page_id, "vector": {"original": vector}, "payload": {
                    "page_id": page_id, "document_id": doc.id, "document_version_id": version.id,
                    "profile_id": profile_id, "index_generation": candidate_id, "owner_id": doc.owner_id,
                    "visibility": doc.visibility, "render_sha256": entry["render_sha256"], "embedding_sha256": encoded["embedding_sha256"]}})
            checkpoint("indexing", 80)
            phase = "indexing"
            self.qdrant.check_info(self.qdrant.info(old.collection_name), old.page_count)
            previous = self.qdrant.all_points(old.collection_name)
            if len(previous) != len(memberships) or {str(p["id"]) for p in previous} != set(memberships):
                raise IngestError("ACTIVE_INDEX_INCOMPLETE")
            for point in previous:
                payload = point["payload"]
                if (set(point["vector"]) != {"original"} or payload.get("index_generation") != old_id
                        or payload.get("profile_id") != profile_id or payload.get("page_id") != str(point["id"])
                        or payload.get("embedding_sha256") != memberships[str(point["id"])]
                        or any(payload.get(k) != v for k, v in old_identities[str(point["id"])].items())
                        or feature_digest(validate_vector(point["vector"]["original"], rows=1031)) != memberships[str(point["id"])]):
                    raise IngestError("ACTIVE_INDEX_IDENTITY_MISMATCH")
                point["payload"] = {**payload, "index_generation": candidate_id}
            all_points = previous + points
            collection = "layoutpatch_system_ingest_" + candidate_id.replace("-", "")
            provenance = canonical({"schema": "copy-on-write-full-index-v1", "parent_index": old_id,
                                    "parent_feature_sha256": old.feature_file_sha256,
                                    "new_features": [f[2]["tensor_sha256"] for f in features],
                                    "pdf_sha256": version.pdf_sha256, "render_profile": manifest["render_profile"],
                                    "pages": [{"id": p["id"], "payload": p["payload"]} for p in all_points]})
            with write_transaction(self.engine) as db:
                db.add(IndexGeneration(id=candidate_id, profile_id=profile_id, collection_name=collection, status="building"))
            if self.qdrant.info(collection) is not None:
                raise IngestError("CANDIDATE_COLLECTION_EXISTS")
            self.qdrant.create(collection)
            for point in all_points:
                checkpoint()
                self.qdrant.upsert(collection, [point])
            self.qdrant.check_info(self.qdrant.info(collection), len(all_points))
            actual = self.qdrant.all_points(collection)
            lookup = {str(p["id"]): p for p in actual}
            if len(actual) != len(all_points) or len(lookup) != len(all_points):
                raise IngestError("CANDIDATE_INDEX_INCOMPLETE")
            for expected in all_points:
                received = lookup.get(str(expected["id"]))
                if (received is None or received["payload"] != expected["payload"] or set(received["vector"]) != {"original"}
                        or feature_digest(validate_vector(received["vector"]["original"], rows=1031)) != expected["payload"]["embedding_sha256"]):
                    raise IngestError("CANDIDATE_INDEX_IDENTITY_MISMATCH")
            checkpoint("activating", 95)
            phase = "activating"
            (output / "index-provenance.json").write_text(provenance + "\n", encoding="utf-8")
            with write_transaction(self.engine) as db:
                current, _ = active_index(db)
                current_job = db.get(Job, job_id)
                current_doc = db.get(Document, doc.id)
                current_user = db.get(User, job.owner_id)
                current_version = db.get(DocumentVersion, version.id)
                if current_job.cancel_requested_at:
                    raise IngestError("CANCELLED_BY_OWNER")
                if self.stop_event.is_set():
                    raise IngestError("INGEST_INTERRUPTED")
                if time.monotonic() >= deadline:
                    raise IngestError("INGEST_DEADLINE_EXCEEDED")
                if (current.id != old_id or index_epoch(db) != old_epoch or not current_user.active or current_job.status != "running"
                        or current_job.attempt != attempt
                        or current_doc.owner_id != job.owner_id or current_doc.status != "registered" or current_doc.deleted_at
                        or current_doc.active_version_id is not None or current_version.pdf_sha256 != version.pdf_sha256):
                    raise IngestError("INGEST_AUTHORITY_CHANGED")
                for page_id, entry, encoded in features:
                    db.add(Page(id=page_id, document_version_id=version.id, source_page_id=f"upload:{version.id}:p{entry['page_index']}",
                                **{key: entry[key] for key in ("page_index", "width_px", "height_px", "render_sha256", "image_path")}))
                db.flush()
                for page_id, entry, encoded in features:
                    db.add(PageFeature(page_id=page_id, encoder_sha256=encoder_sha,
                                       **{key: encoded[key] for key in ("tensor_path", "tensor_sha256", "export_path", "export_sha256")}))
                for point in all_points:
                    db.add(IndexPage(index_id=candidate_id, page_id=str(point["id"]), embedding_sha256=point["payload"]["embedding_sha256"], token_count=1031))
                candidate = db.get(IndexGeneration, candidate_id)
                candidate.status, candidate.page_count, candidate.vector_count = "ready", len(all_points), len(all_points) * 1031
                candidate.feature_file_sha256 = sha(canonical({"parent": old.feature_file_sha256, "tensors": [f[2]["tensor_sha256"] for f in features]}).encode())
                candidate.source_manifest_sha256 = sha(provenance.encode())
                current_version.render_profile_json, current_version.render_profile_sha256 = render_json, sha(render_json.encode())
                current_doc.status, current_doc.active_version_id = "ready", version.id
                current_job.status, current_job.stage, current_job.progress, current_job.updated_at = "completed", "completed", 100, now()
                sync_attempt(db, current_job)
                state = db.get(SystemState, 1)
                if state is None:
                    db.add(SystemState(id=1, active_index_id=candidate_id, index_epoch=old_epoch+1))
                else:
                    state.active_index_id = candidate_id
                    state.index_epoch += 1
        except Exception as exc:
            if isinstance(exc, IngestError):
                code = exc.code
            elif isinstance(exc, SearchBusy):
                code = "MODEL_BUSY"
            elif isinstance(exc, SearchUnavailable):
                code = "PAGE_ENCODING_FAILED" if phase == "encoding" else "INDEX_UNAVAILABLE"
            elif isinstance(exc, subprocess.TimeoutExpired):
                code = "RENDER_TIMEOUT"
            elif isinstance(exc, OSError):
                code = "INGEST_STORAGE_FAILED"
            elif isinstance(exc, SQLAlchemyError):
                code = "METADATA_UNAVAILABLE"
            else:
                code = "INGEST_FAILED"
            with write_transaction(self.engine) as db:
                failed = db.get(Job, job_id)
                # Never undo a committed activation due to post-commit filesystem failure.
                if failed and failed.status == "running" and failed.attempt == attempt:
                    if failed.cancel_requested_at:
                        code = "CANCELLED_BY_OWNER"
                    failed.status = "cancelled" if code == "CANCELLED_BY_OWNER" else "interrupted" if code == "INGEST_INTERRUPTED" else "failed"
                    failed.error_code, failed.updated_at = code, now()
                    sync_attempt(db, failed)
                if candidate_id:
                    candidate = db.get(IndexGeneration, candidate_id)
                    if candidate and candidate.status == "building":
                        candidate.status = "failed"
        return True
