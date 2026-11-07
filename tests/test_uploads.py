"""Real SQLite/filesystem upload contracts; no model, MinerU or Qdrant execution."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.settings import AuthSettings
from backend.db.connection import ROOT
from backend.db.models import Document, DocumentVersion, Job, User
from backend.db.seed import password_hasher, sha
from backend.documents.uploads import UploadSettings, write_pdf
from backend.main import create_app
from scripts.migrate_database import migrate

ORIGIN = "http://127.0.0.1:3000"


def pdf_bytes(pages=1, encrypted=False, width=200):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=300)
    if encrypted:
        writer.encrypt("test-only")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class UploadTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "runtime/verification").mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="r14-upload-", dir=ROOT / "runtime/verification")
        self.base = Path(self.temp.name)
        self.database = self.base / "metadata.sqlite3"
        migrate(self.database)
        self.settings = AuthSettings(database=self.database)
        self.upload_settings = UploadSettings(root=self.base / "files", max_bytes=2048, max_pages=2)
        self.app = create_app(self.settings, upload_settings=self.upload_settings, ingestion_enabled=False)
        self.password = secrets.token_urlsafe(24)
        with Session(self.app.state.engine) as db:
            for name in ("A", "B", "admin", "first"):
                db.add(User(username=name, role="admin" if name == "admin" else "user",
                            password_hash=password_hasher.hash(self.password), must_change_password=name == "first"))
            db.commit()
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def login(self, name="A", client=None):
        response = (client or self.client).post("/auth/login", json={"username": name, "password": self.password}, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf_token"]

    def upload(self, csrf, data=None, key=None, name="same.pdf", client=None, headers=None, files=None, **kwargs):
        if isinstance(data, dict):
            kwargs["data"] = data
        return (client or self.client).post("/index", headers=headers if headers is not None else {
            "Origin": ORIGIN, "X-CSRF-Token": csrf, "X-Upload-ID": key or str(uuid4())},
            files=files if files is not None else {"file": (name, data if data is not None else pdf_bytes(), "application/pdf")}, **kwargs)

    def status(self, response, expected):
        self.assertEqual(response.status_code, expected, response.text)
        self.assertEqual(response.headers.get("cache-control"), "private, no-store")
        self.assertEqual(response.headers.get("vary"), "Cookie")
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_auth_first_change_and_status_routes(self):
        self.status(self.upload("bad"), 401)
        self.status(self.client.get("/jobs/unknown"), 401)
        self.status(self.client.get("/documents/unknown"), 401)
        csrf = self.login("first")
        self.status(self.upload(csrf), 403)
        self.status(self.client.get("/jobs/unknown"), 403)

    def test_origin_csrf_and_json_remain_enforced(self):
        csrf = self.login()
        for origin in (None, "null", "https://attacker.invalid"):
            headers = {"X-CSRF-Token": csrf, "X-Upload-ID": str(uuid4())}
            if origin:
                headers["Origin"] = origin
            self.status(self.upload(csrf, headers=headers), 403)
        self.status(self.upload(csrf, headers=[("Origin", ORIGIN), ("Origin", ORIGIN)]), 403)
        self.status(self.upload(csrf, headers={"Origin": ORIGIN, "Sec-Fetch-Site": "cross-site"}), 403)
        self.status(self.upload(csrf, headers={"Origin": ORIGIN}), 403)
        self.status(self.upload(csrf, headers=[("Origin", ORIGIN), ("X-CSRF-Token", csrf), ("X-CSRF-Token", csrf)]), 403)
        self.status(self.client.post("/index", json={}, headers={"Origin": ORIGIN}), 415)
        self.status(self.client.post("/auth/logout", files={"file": ("a.pdf", pdf_bytes())}, headers={"Origin": ORIGIN}), 415)

    def test_private_same_name_cross_user_and_admin_have_no_bypass(self):
        csrf = self.login()
        first = self.upload(csrf).json()
        self.status(self.client.get("/jobs/" + first["job_id"]), 200)
        doc = self.client.get("/documents/" + first["document_id"])
        self.status(doc, 200)
        self.assertEqual((doc.json()["visibility"], doc.json()["status"], doc.json()["version"]), ("private", "registered", 1))
        for name in ("B", "admin"):
            csrf = self.login(name)
            self.status(self.client.get("/jobs/" + first["job_id"]), 404)
            self.status(self.client.get("/documents/" + first["document_id"]), 404)
        second = self.upload(self.login("B"), data=pdf_bytes(width=250)).json()
        self.assertNotEqual(first["document_id"], second["document_id"])
        with Session(self.app.state.engine) as db:
            docs = db.scalars(select(Document)).all()
            self.assertEqual(len({d.owner_id for d in docs}), 2)
            self.assertTrue(all(d.active_version_id is None and d.status == "registered" and d.visibility == "private" for d in docs))
            versions = db.scalars(select(DocumentVersion)).all()
            self.assertEqual(len({v.pdf_path for v in versions}), 2)
            self.assertEqual(len({v.pdf_sha256 for v in versions}), 2)
            for version in versions:
                self.assertEqual(sha((ROOT / version.pdf_path).read_bytes()), version.pdf_sha256)
                self.assertNotIn(version.pdf_path, doc.text)

    def test_repeated_key_conflict_new_key_and_owner_scoping(self):
        csrf, key = self.login(), str(uuid4())
        first = self.upload(csrf, key=key)
        self.status(first, 202)
        self.assertEqual(self.upload(csrf, key=key).json(), first.json())
        self.status(self.upload(csrf, key=key, data=pdf_bytes(width=250)), 409)
        self.status(self.upload(csrf, key=key, name="other.pdf"), 409)
        second = self.upload(csrf)
        self.assertNotEqual(second.json()["job_id"], first.json()["job_id"])
        self.status(self.upload(self.login("B"), key=key), 202)
        self.status(self.upload(csrf, headers={"Origin": ORIGIN, "X-CSRF-Token": self.login("B"), "X-Upload-ID": "invalid"}), 422)

    def test_fields_filename_multipart_and_parser_validation(self):
        csrf = self.login()
        for name in ("../a.pdf", "x.txt"):
            self.status(self.upload(csrf, name=name), 422)
        for data in (b"fake", b"%PDF-1.7\ninvalid", pdf_bytes(pages=0), pdf_bytes(encrypted=True)):
            self.status(self.upload(csrf, data=data), 422)
        self.status(self.upload(csrf, files={"file": ("a.pdf", pdf_bytes(), "image/png")}), 415)
        for field in ("owner_id", "visibility", "document_id", "path", "role"):
            self.status(self.upload(csrf, data={field: "anything"}, files={"file": ("a.pdf", pdf_bytes(), "application/pdf")}), 422)
        self.status(self.upload(csrf, files=[("file", ("a.pdf", pdf_bytes(), "application/pdf")), ("file", ("b.pdf", pdf_bytes(), "application/pdf"))]), 422)
        self.status(self.client.post("/index", content=b"bad", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf,
                    "X-Upload-ID": str(uuid4()), "Content-Type": "multipart/form-data"}), 422)
        with Session(self.app.state.engine) as db:
            self.assertEqual(len(db.scalars(select(Job)).all()), 0)

    def test_file_pages_and_streamed_body_limits(self):
        csrf = self.login()
        self.status(self.upload(csrf, data=pdf_bytes() + b" " * 2048), 413)
        self.status(self.upload(csrf, data=pdf_bytes(pages=3)), 413)
        self.status(self.client.post("/index", content=iter([b"x" * 35000] * 2), headers={
            "Origin": ORIGIN, "Content-Type": "multipart/form-data; boundary=test"}), 413)

    def test_write_failure_is_durable_no_search_activation_and_no_retry_side_effect(self):
        csrf, key = self.login(), str(uuid4())
        def partial(path, data):
            path.parent.mkdir(parents=True)
            path.with_suffix(".part").write_bytes(data[:20])
            raise OSError("private disk details")
        with patch("backend.documents.ingest.write_pdf", side_effect=partial):
            response = self.upload(csrf, key=key)
        self.status(response, 503)
        self.assertNotIn("private disk details", response.text)
        result = self.client.get("/jobs/" + response.json()["job_id"]).json()
        self.assertEqual((result["status"], result["attempt"], result["error_code"]), ("failed", 1, "UPLOAD_WRITE_FAILED"))
        self.assertEqual(self.upload(csrf, key=key).json(), result)
        self.assertFalse(any(self.upload_settings.root.rglob("*.part")))
        self.assertFalse(any(self.upload_settings.root.rglob("*.pdf")))

    def test_restart_queued_files_and_interrupted_reservation(self):
        csrf = self.login()
        first = self.upload(csrf).json()
        with Session(self.app.state.engine) as db:
            second = db.get(Job, first["job_id"])
            second.status = "receiving"
            db.commit()
        app = create_app(self.settings, upload_settings=self.upload_settings, ingestion_enabled=False)
        with TestClient(app) as client:
            client.cookies.update(self.client.cookies)
            result = client.get("/jobs/" + first["job_id"])
            self.status(result, 200)
            self.assertEqual(result.json()["status"], "interrupted")
            self.assertEqual(result.json()["error_code"], "UPLOAD_INTERRUPTED")
        # Also establish queued survives another app lifecycle, with same bytes/hash.
        queued = self.upload(csrf).json()
        with TestClient(create_app(self.settings, upload_settings=self.upload_settings, ingestion_enabled=False)) as client:
            client.cookies.update(self.client.cookies)
            self.assertEqual(client.get("/jobs/" + queued["job_id"]).json(), queued)

    def test_concurrent_same_key_has_one_reservation(self):
        csrf, key = self.login(), str(uuid4())
        # No extra lifespan starts during live uploads (single-worker contract).
        def send_no_lifespan():
            client = TestClient(self.app)
            try:
                client.cookies.update(self.client.cookies)
                return self.upload(csrf, key=key, client=client)
            finally:
                client.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: send_no_lifespan(), range(2)))
        self.assertTrue(all(r.status_code in (202, 409) for r in results))
        self.assertIn(202, [r.status_code for r in results])
        with Session(self.app.state.engine) as db:
            self.assertEqual(len(db.scalars(select(Job)).all()), 1)

    def test_revocation_during_disk_write_cannot_queue(self):
        csrf = self.login()
        def revoke(path, data):
            write_pdf(path, data)
            with Session(self.app.state.engine) as db:
                user = db.scalar(select(User).where(User.username == "A"))
                user.active = False
                db.commit()
        with patch("backend.documents.ingest.write_pdf", side_effect=revoke):
            self.status(self.upload(csrf), 401)
        with Session(self.app.state.engine) as db:
            self.assertEqual(db.scalar(select(Job)).status, "failed")
            self.assertIsNone(db.scalar(select(Document)).active_version_id)
        self.assertFalse(any(self.upload_settings.root.rglob("*.pdf")))


if __name__ == "__main__":
    unittest.main()
