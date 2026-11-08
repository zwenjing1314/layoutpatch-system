"""New pipeline transaction/failure tests. Encoder/vector doubles are not GPU evidence."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from PIL import Image
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT
from backend.db.models import Document, DocumentVersion, IndexGeneration, IndexPage, Job, Page, PageFeature, SystemState, User
from backend.db.seed import sha
from backend.documents.ingest import recover_uploads
from backend.documents.pipeline import IngestionRunner
from backend.documents.uploads import UploadSettings
from backend.search.indexing import feature_digest
from backend.search.qdrant import Qdrant, SearchUnavailable
from backend.search.scope import active_index, allowed_scope
from tests import test_search as search_tests
from tests.test_uploads import pdf_bytes


VECTOR = [[1.0] + [0.0] * 127 for _ in range(1031)]


class MemoryQdrant:
    check_info = staticmethod(lambda info, count: (_ for _ in ()).throw(SearchUnavailable()) if info is None or info["count"] != count else None)

    def __init__(self, engine):
        self.collections, self.callback, self.fail_at, self.writes = {}, None, None, 0
        with Session(engine) as db:
            index, profile = active_index(db)
            rows = []
            for page, doc, ip in db.execute(select(Page, Document, IndexPage).join(DocumentVersion, DocumentVersion.id == Page.document_version_id)
                       .join(Document, Document.id == DocumentVersion.document_id).join(IndexPage, IndexPage.page_id == Page.id)):
                rows.append({"id": page.id, "vector": {"original": VECTOR}, "payload": {"page_id": page.id,
                    "document_id": doc.id, "document_version_id": page.document_version_id, "profile_id": profile.id,
                    "index_generation": index.id, "owner_id": doc.owner_id, "visibility": doc.visibility,
                    "render_sha256": page.render_sha256, "embedding_sha256": feature_digest(VECTOR)}})
                ip.embedding_sha256 = feature_digest(VECTOR)
            db.commit()
            self.collections[index.collection_name] = rows

    def info(self, name):
        return {"count": len(self.collections[name])} if name in self.collections else None

    def all_points(self, name):
        return deepcopy(self.collections[name])

    def create(self, name):
        self.collections[name] = []

    def upsert(self, name, points):
        self.writes += 1
        if self.callback:
            self.callback()
        if self.fail_at == self.writes:
            raise SearchUnavailable()
        self.collections[name].extend(deepcopy(points))


class PageEncoder:
    def __init__(self):
        self.calls, self.fail_at = 0, None

    def encode_page(self, image_path, stem, render_sha256, expected_profile):
        self.calls += 1
        if self.calls == self.fail_at:
            raise SearchUnavailable()
        tensor, export = stem.with_suffix(".pt"), stem.with_suffix(".json")
        tensor.write_bytes(b"unit-test-double-not-real-tensor")
        export.write_text(json.dumps(VECTOR))
        return {"profile_sha256": expected_profile, "network_attempts": 0, "token_count": 1031, "dimension": 128,
                "patch_tokens": 1024, "embedding_sha256": feature_digest(VECTOR),
                "tensor_path": tensor.relative_to(ROOT).as_posix(), "tensor_sha256": sha(tensor.read_bytes()),
                "export_path": export.relative_to(ROOT).as_posix(), "export_sha256": sha(export.read_bytes())}


def renderer(worker, version, output):
    output.mkdir(parents=True)
    entries = []
    for number in range(version.page_count):
        image = output / f"page-{number:04}.png"
        Image.new("RGB", (100, 120), "white").save(image)
        entries.append({"page_index": number, "width_px": 100, "height_px": 120,
                        "image_path": image.relative_to(ROOT).as_posix(), "render_sha256": sha(image.read_bytes())})
    return {"pdf_sha256": version.pdf_sha256, "render_profile": {"unit_test_renderer": True, "dpi": 144, "colorspace": "RGB", "format": "PNG"}, "pages": entries}


class IngestionTests(unittest.TestCase):
    def setUp(self):
        search_tests.SearchTests.setUp(self)
        self.app.state.ingestion.close()
        self.app.state.upload_settings = UploadSettings(root=self.path.parent / "uploads")

    login = search_tests.SearchTests.login

    def tearDown(self):
        for path in getattr(self, "artifact_dirs", []):
            if path.is_relative_to((ROOT / "runtime/corpus/ingest").resolve()):
                shutil.rmtree(path, ignore_errors=True)
        search_tests.SearchTests.tearDown(self)

    def prepare(self, pages=2):
        csrf = self.login()["csrf_token"]
        import uuid
        r = self.client.post("/index", files={"file": ("same.pdf", pdf_bytes(pages=pages), "application/pdf")}, headers={
            "Origin": "http://127.0.0.1:3000", "X-CSRF-Token": csrf, "X-Upload-ID": str(uuid.uuid4())})
        self.assertEqual(r.status_code, 202)
        self.job_id = r.json()["job_id"]
        # Existing SearchTests app scheduler is idle until this upload. Stop it before
        # manually driving the isolated test; no real model operation is allowed.
        self.q = MemoryQdrant(self.engine)
        self.encoder = PageEncoder()
        self.runner = IngestionRunner(self.engine, self.encoder, self.q, renderer)
        self.artifact_dirs = [(ROOT / "runtime/corpus/ingest" / self.job_id).resolve()]
        with Session(self.engine) as db:
            self.old_id = active_index(db)[0].id
            self.old_collection = active_index(db)[0].collection_name
            self.old_scope = allowed_scope(db, db.scalar(select(User).where(User.username == "A")))
        self.old_points = deepcopy(self.q.collections[self.old_collection])

    def status(self):
        with Session(self.engine) as db:
            return db.get(Job, self.job_id).status

    def test_full_activation_and_all_pages_are_correlated(self):
        self.prepare()
        seen_old = []
        def during_write():
            with Session(self.engine) as db:
                seen_old.append(active_index(db)[0].id)
                self.assertEqual(allowed_scope(db, db.scalar(select(User).where(User.username == "A"))), self.old_scope)
        self.q.callback = during_write
        self.assertTrue(self.runner.run_one())
        self.assertEqual(self.status(), "completed")
        self.assertEqual(self.encoder.calls, 2)
        self.assertEqual(set(seen_old), {self.old_id})
        self.assertEqual(self.q.collections[self.old_collection], self.old_points)
        with Session(self.engine) as db:
            index, _ = active_index(db)
            self.assertEqual(index.page_count, 15)
            self.assertNotEqual(index.id, self.old_id)
            self.assertEqual(len(db.scalars(select(PageFeature)).all()), 2)
            self.assertEqual(len(allowed_scope(db, db.scalar(select(User).where(User.username == "A"))).pages), 7)
            self.assertEqual(len(allowed_scope(db, db.scalar(select(User).where(User.username == "B"))).pages), 8)
            self.assertEqual(len(allowed_scope(db, db.scalar(select(User).where(User.username == "admin"))).pages), 0)
            job = db.get(Job, self.job_id)
            doc = db.get(Document, db.get(DocumentVersion, job.document_version_id).document_id)
            self.assertEqual(doc.active_version_id, job.document_version_id)
        self.assertFalse(self.runner.run_one())

    def test_mid_encoding_failure_leaves_old_search_and_no_staged_pages(self):
        self.prepare()
        self.encoder.fail_at = 2
        self.runner.run_one()
        self.assertEqual(self.status(), "failed")
        with Session(self.engine) as db:
            self.assertEqual(db.get(Job, self.job_id).error_code, "PAGE_ENCODING_FAILED")
        self.assert_unchanged()

    def assert_unchanged(self):
        with Session(self.engine) as db:
            self.assertEqual(active_index(db)[0].id, self.old_id)
            self.assertEqual(allowed_scope(db, db.scalar(select(User).where(User.username == "A"))), self.old_scope)
            self.assertEqual(len(db.scalars(select(Page)).all()), 13)
            self.assertEqual(len(db.scalars(select(PageFeature)).all()), 0)
        self.assertEqual(self.q.collections[self.old_collection], self.old_points)

    def test_partial_qdrant_write_failure_keeps_old_index_active(self):
        self.prepare()
        self.q.fail_at = 3
        self.runner.run_one()
        self.assertEqual(self.status(), "failed")
        self.assert_unchanged()
        with Session(self.engine) as db:
            self.assertEqual(len(db.scalars(select(IndexGeneration).where(IndexGeneration.status == "failed")).all()), 1)

    def test_sqlite_activation_failure_rolls_back_all_new_metadata(self):
        self.prepare()
        def reject(mapper, connection, target):
            raise RuntimeError("injected PageFeature persistence failure")
        event.listen(PageFeature, "before_insert", reject)
        try:
            self.runner.run_one()
        finally:
            event.remove(PageFeature, "before_insert", reject)
        self.assertEqual(self.status(), "failed")
        self.assert_unchanged()

    def test_owner_disabled_during_indexing_cannot_activate(self):
        self.prepare()
        def disable():
            with Session(self.engine) as db, db.begin():
                db.scalar(select(User).where(User.username == "A")).active = False
        self.q.callback = disable
        self.runner.run_one()
        self.assertEqual(self.status(), "failed")
        self.assert_unchanged()

    def test_running_and_candidate_recovery_never_activates(self):
        self.prepare()
        with Session(self.engine) as db, db.begin():
            db.get(Job, self.job_id).status = "running"
        recover_uploads(self.engine)
        self.assertEqual(self.status(), "interrupted")
        self.assert_unchanged()

    def test_active_index_aba_epoch_during_ingestion_rejects_activation(self):
        self.prepare(pages=1)
        def aba():
            self.q.callback = None
            with Session(self.engine) as db, db.begin():
                state = db.get(SystemState, 1)
                state.active_index_id, state.index_epoch = self.old_id, state.index_epoch + 2
        self.q.callback = aba
        self.runner.run_one()
        self.assertEqual(self.status(), "failed")
        with Session(self.engine) as db:
            self.assertEqual(active_index(db)[0].id, self.old_id)
            self.assertEqual(db.get(SystemState, 1).index_epoch, 3)
            self.assertEqual(db.get(Job, self.job_id).error_code, "INGEST_AUTHORITY_CHANGED")
            self.assertEqual(len(db.scalars(select(Page)).all()), 13)
        self.assertEqual(self.q.collections[self.old_collection], self.old_points)

    def test_copied_payload_or_vector_mismatch_refuses_activation(self):
        self.prepare()
        self.q.collections[self.old_collection][0]["payload"]["document_version_id"] = "wrong-version"
        tampered = deepcopy(self.q.collections[self.old_collection])
        self.runner.run_one()
        self.assertEqual(self.status(), "failed")
        with Session(self.engine) as db:
            self.assertEqual(active_index(db)[0].id, self.old_id)
            self.assertEqual(db.get(Job, self.job_id).error_code, "ACTIVE_INDEX_IDENTITY_MISMATCH")
        self.assertEqual(self.q.collections[self.old_collection], tampered)

    def test_feature_encoder_mismatch_refuses_activation(self):
        self.prepare()
        original = self.encoder.encode_page
        def wrong(*args):
            return {**original(*args), "profile_sha256": "0" * 64}
        self.encoder.encode_page = wrong
        self.runner.run_one()
        self.assertEqual(self.status(), "failed")
        self.assert_unchanged()


if __name__ == "__main__":
    unittest.main()
