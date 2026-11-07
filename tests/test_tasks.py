"""Real SQLite task contracts; pipeline uses explicit encoder/vector doubles."""
from concurrent.futures import ThreadPoolExecutor
import time
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Document, DocumentVersion, Job, JobAttempt, now
from backend.documents.ingest import recover_uploads
from backend.documents.task_state import sync_attempt
from tests import test_ingestion as ing
from tests import test_uploads as uploads

ORIGIN = uploads.ORIGIN


class TaskRouteTests(unittest.TestCase):
    setUp = uploads.UploadTests.setUp
    tearDown = uploads.UploadTests.tearDown
    login = uploads.UploadTests.login
    upload = uploads.UploadTests.upload
    status = uploads.UploadTests.status

    def create(self):
        self.csrf = self.login()
        response = self.upload(self.csrf)
        self.status(response, 202)
        return response.json()

    def action(self, job, action, attempt=1, client=None, csrf=None):
        return (client or self.client).post(f"/jobs/{job['job_id']}/{action}", json={"attempt": attempt},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf or self.csrf})

    def test_owned_list_no_admin_bypass_and_auth_write_boundaries(self):
        job = self.create()
        self.status(self.client.get("/jobs"), 200)
        self.assertEqual(self.client.get("/jobs").json()["items"][0]["job_id"], job["job_id"])
        for action in ("cancel", "retry"):
            self.status(self.client.post(f"/jobs/{job['job_id']}/{action}", json={"attempt": 1}, headers={"Origin": ORIGIN}), 403)
            self.status(self.client.post(f"/jobs/{job['job_id']}/{action}", json={"attempt": 1}, headers={"Origin": "https://bad.invalid", "X-CSRF-Token": self.csrf}), 403)
            self.status(self.client.post(f"/jobs/{job['job_id']}/{action}", json={"attempt": 1, "owner_id": "other"}, headers={"Origin": ORIGIN, "X-CSRF-Token": self.csrf}), 422)
        for name in ("B", "admin"):
            with TestClient(self.app) as other:
                csrf = self.login(name, other)
                self.assertEqual(other.get("/jobs").json()["items"], [])
                self.status(other.get("/jobs/" + job["job_id"]), 404)
                for action in ("cancel", "retry"):
                    self.status(self.action(job, action, client=other, csrf=csrf), 404)
        with TestClient(self.app) as anonymous:
            self.status(anonymous.get("/jobs"), 401)
        with TestClient(self.app) as first:
            self.login("first", first)
            self.status(first.get("/jobs"), 403)

    def test_queue_cancel_retry_history_and_stale_actions(self):
        job = self.create()
        cancelled = self.action(job, "cancel").json()
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(cancelled["retry_available"])
        self.assertFalse(cancelled["cancel_available"])
        self.status(self.action(job, "cancel"), 200)
        retry = self.action(job, "retry")
        self.status(retry, 200)
        self.assertEqual((retry.json()["attempt"], retry.json()["status"]), (2, "queued"))
        self.assertEqual([a["status"] for a in retry.json()["attempts"]], ["cancelled", "queued"])
        for action in ("cancel", "retry"):
            self.status(self.action(job, action), 409)
        self.assertEqual(self.client.get("/jobs/" + job["job_id"]).json()["status"], "queued")
        self.status(self.action(job, "retry", 2), 409)

    def test_concurrent_retry_only_one_new_attempt(self):
        job = self.create()
        self.action(job, "cancel")
        def retry():
            return self.action(job, "retry").status_code
        with ThreadPoolExecutor(2) as pool:
            codes = list(pool.map(lambda _: retry(), range(2)))
        self.assertEqual(sorted(codes), [200, 409])
        current = self.client.get("/jobs/" + job["job_id"]).json()
        self.assertEqual(current["attempt"], 2)
        self.assertEqual(len(current["attempts"]), 2)

    def test_list_cursor_is_session_and_limit_bound_and_progress_tolerant(self):
        self.create()
        for _ in range(3):
            self.upload(self.csrf)
        first = self.client.get("/jobs?limit=2").json()
        cursor = first["next_cursor"]
        second = self.client.get("/jobs", params={"limit": 2, "cursor": cursor})
        self.status(second, 200)
        ids = [j["job_id"] for j in first["items"] + second.json()["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 4)
        self.status(self.client.get("/jobs", params={"limit": 1, "cursor": cursor}), 422)
        self.status(self.client.get("/jobs", params={"limit": 2, "cursor": cursor + "x"}), 422)
        for suffix in ("?limit=0", "?limit=2&limit=2", "?owner_id=B", "?cursor="):
            self.status(self.client.get("/jobs" + suffix), 422)
        with TestClient(self.app) as same_user:
            self.login("A", same_user)
            self.status(same_user.get("/jobs", params={"limit": 2, "cursor": cursor}), 422)

    def test_missing_or_changed_source_and_max_attempt_refuse_retry(self):
        job = self.create()
        self.action(job, "cancel")
        with Session(self.app.state.engine) as db:
            record = db.get(Job, job["job_id"])
            version = db.get(DocumentVersion, record.document_version_id)
            from backend.db.connection import ROOT
            source = ROOT / version.pdf_path
        original = source.read_bytes()
        source.write_bytes(b"changed")
        response = self.action(job, "retry")
        self.status(response, 409)
        self.assertEqual(response.json()["detail"], "REUPLOAD_REQUIRED")
        source.unlink()
        self.assertFalse(self.client.get("/jobs/" + job["job_id"]).json()["retry_available"])
        self.status(self.action(job, "retry"), 409)
        source.write_bytes(original)
        with Session(self.app.state.engine) as db, db.begin():
            record = db.get(Job, job["job_id"])
            record.attempt = 10
            sync_attempt(db, record)
        self.status(self.action(job, "retry", 10), 409)


class TaskPipelineTests(unittest.TestCase):
    setUp = ing.IngestionTests.setUp
    tearDown = ing.IngestionTests.tearDown
    login = ing.IngestionTests.login
    prepare = ing.IngestionTests.prepare
    status = ing.IngestionTests.status
    assert_unchanged = ing.IngestionTests.assert_unchanged

    def action(self, action, attempt=1):
        csrf = self.client.get("/auth/me").json()["csrf_token"]
        return self.client.post(f"/jobs/{self.job_id}/{action}", json={"attempt": attempt}, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})

    def test_cancel_during_render_discards_before_page_encoding(self):
        self.prepare()
        original = self.runner.renderer
        def render(*args):
            response = self.action("cancel")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "running")
            self.assertTrue(response.json()["cancel_requested_at"])
            self.assertFalse(response.json()["retry_available"])
            return original(*args)
        self.runner.renderer = render
        self.runner.run_one()
        self.assertEqual(self.status(), "cancelled")
        self.assertEqual(self.encoder.calls, 0)
        self.assert_unchanged()

    def test_cancel_after_page_forward_before_index_does_not_activate(self):
        self.prepare(pages=1)
        original = self.encoder.encode_page
        def encode(*args):
            result = original(*args)
            self.action("cancel")
            return result
        self.encoder.encode_page = encode
        self.runner.run_one()
        self.assertEqual(self.encoder.calls, 1)
        self.assertEqual(self.status(), "cancelled")
        self.assertEqual(self.q.writes, 0)
        self.assert_unchanged()

    def test_cancel_after_final_checkpoint_is_rechecked_inside_activation(self):
        self.prepare()
        original = self.runner.checkpoint
        def checkpoint(*args, **kwargs):
            original(*args, **kwargs)
            if len(args) > 1 and args[1] == "activating":
                self.assertEqual(self.action("cancel").status_code, 200)
        self.runner.checkpoint = checkpoint
        self.runner.run_one()
        self.assertEqual(self.status(), "cancelled")
        self.assert_unchanged()

    def test_index_cancel_failed_candidate_retry_and_completed_not_repeated(self):
        self.prepare()
        self.q.callback = lambda: self.action("cancel")
        self.runner.run_one()
        self.assertEqual(self.status(), "cancelled")
        self.assert_unchanged()
        self.q.callback = None
        self.assertEqual(self.action("retry").status_code, 200)
        self.runner.run_one()
        self.assertEqual(self.status(), "completed")
        current = self.client.get("/jobs/" + self.job_id).json()
        self.assertEqual([a["status"] for a in current["attempts"]], ["cancelled", "completed"])
        self.assertEqual(current["attempt"], 2)
        self.assertFalse(current["retry_available"])
        self.assertFalse(self.runner.run_one())
        self.assertEqual(self.action("cancel", 2).status_code, 409)
        self.assertEqual(self.action("retry", 2).status_code, 409)

    def test_failed_encoding_retries_with_distinct_attempt_output(self):
        self.prepare()
        self.encoder.fail_at = 2
        self.runner.run_one()
        self.assertEqual(self.status(), "failed")
        self.assertEqual(self.action("retry").status_code, 200)
        self.encoder.fail_at = None
        self.runner.run_one()
        self.assertEqual(self.status(), "completed")
        from backend.db.connection import ROOT
        self.assertTrue((ROOT / "runtime/corpus/ingest" / self.job_id / "attempt-1").is_dir())
        self.assertTrue((ROOT / "runtime/corpus/ingest" / self.job_id / "attempt-2").is_dir())
        response = self.client.get("/jobs/" + self.job_id).json()
        self.assertEqual([a["status"] for a in response["attempts"]], ["failed", "completed"])

    def test_recovery_preserves_history_and_honors_saved_cancel(self):
        self.prepare()
        with Session(self.engine) as db, db.begin():
            job = db.get(Job, self.job_id)
            job.status, job.cancel_requested_at = "running", now()
            sync_attempt(db, job)
        recover_uploads(self.engine)
        response = self.client.get("/jobs/" + self.job_id).json()
        self.assertEqual(response["status"], "cancelled")
        self.assertEqual(response["attempts"][0]["status"], "cancelled")
        self.assertTrue(response["retry_available"])
        self.assert_unchanged()
        self.action("retry")
        with Session(self.engine) as db, db.begin():
            job = db.get(Job, self.job_id)
            job.status = "running"
            sync_attempt(db, job)
        recover_uploads(self.engine)
        response = self.client.get("/jobs/" + self.job_id).json()
        self.assertEqual([a["status"] for a in response["attempts"]], ["cancelled", "interrupted"])
        self.assert_unchanged()

    def test_attempt_deadline_is_checked_after_bounded_operation(self):
        self.prepare()
        self.runner.max_seconds = 1
        original = self.runner.renderer
        def render(*args):
            result = original(*args)
            time.sleep(1.02)
            return result
        self.runner.renderer = render
        self.runner.run_one()
        response = self.client.get("/jobs/" + self.job_id).json()
        self.assertEqual(response["error_code"], "INGEST_DEADLINE_EXCEEDED")
        self.assertEqual(response["status"], "failed")
        self.assert_unchanged()
