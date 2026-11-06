"""Real SQLite migration, complete corpus and destructive-input checks in isolated runtime directories."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import hashlib
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.connection import ROOT, make_engine
from backend.db.models import Base, User
from backend.db.seed import MANIFEST, password_hasher, seed, validate_corpus
from scripts.inspect_database import inspect_database
from scripts.migrate_database import migrate


class DatabaseInitializationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "runtime/verification").mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="r08-", dir=ROOT / "runtime/verification")
        self.base = Path(self.temp.name)
        self.path = self.base / "metadata.sqlite3"
        migrate(self.path)
        self.engine = make_engine(self.path)
        self.passwords = {name: secrets.token_urlsafe(24) for name in ("admin", "A", "B")}

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def populate(self):
        return seed(self.engine, self.passwords.__getitem__)

    def snapshot(self):
        # Compare logical contents, not volatile WAL/file bytes; never log credentials.
        with closing(sqlite3.connect(self.path)) as connection:
            return hashlib.sha256("\n".join(connection.iterdump()).encode()).hexdigest()

    def test_migration_repeat_and_metadata_no_drift(self):
        before = self.snapshot()
        migrate(self.path)
        self.assertEqual(before, self.snapshot())
        with self.engine.connect() as c:
            self.assertEqual(c.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)
            self.assertEqual(c.exec_driver_sql("PRAGMA journal_mode").scalar(), "wal")
            self.assertEqual(c.exec_driver_sql("PRAGMA busy_timeout").scalar(), 5000)
            self.assertEqual(compare_metadata(MigrationContext.configure(c), Base.metadata), [])

    def test_real_complete_corpus_ownership_and_hashes(self):
        self.assertEqual(self.populate(), dict(users=3, documents=2, versions=2, pages=13, profiles=1, indexes=1))
        report = inspect_database(self.path)
        self.assertEqual([(d["owner"], d["display_name"], d["registered_pages"]) for d in report["documents"]],
                         [("A", "tuGEMM", 5), ("B", "Music", 8)])
        self.assertEqual(report["integrity_check"], "ok")
        self.assertEqual(report["foreign_key_violations"], [])
        self.assertTrue(all(d["visibility"] == "private" and d["status"] == "registered" for d in report["documents"]))
        self.assertTrue(all(d["first_page_index"] == 0 and d["last_page_index"] == d["page_count"] - 1 for d in report["documents"]))
        self.assertEqual(report["indexes"][0]["status"], "pending")
        self.assertEqual(report["indexes"][0]["vector_count"], 0)
        with Session(self.engine) as session:
            for user in session.scalars(select(User)):
                self.assertTrue(user.password_hash.startswith("$argon2id$"))
                self.assertTrue(password_hasher.verify(self.passwords[user.username], user.password_hash))
                self.assertTrue(user.must_change_password)

    def test_repeat_preserves_password_flags_titles_and_ids(self):
        self.populate()
        with self.engine.begin() as c:
            c.execute(text("UPDATE users SET active=0,must_change_password=0,auth_version=2 WHERE username='A'"))
            c.execute(text("UPDATE documents SET display_name='User edited title' WHERE source_key LIKE '%a9fff%'"))
        before = self.snapshot()
        def no_password_prompt(_):
            self.fail("Repeat seed requested password")
        self.assertTrue(all(n == 0 for n in seed(self.engine, no_password_prompt).values()))
        self.assertEqual(before, self.snapshot())

    def test_conflict_rolls_back_all_new_accounts(self):
        self.populate()
        with self.engine.begin() as c:
            c.execute(text("DELETE FROM users WHERE username='admin'"))
            c.execute(text("UPDATE documents SET owner_id=(SELECT id FROM users WHERE username='B') WHERE source_key LIKE '%a9fff%'"))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.populate()
        self.assertEqual(before, self.snapshot())

    def test_bad_corpus_is_rejected_before_database_writes(self):
        corpus = self.base / "corpus"
        shutil.copytree(MANIFEST.parent, corpus)
        original = json.loads((corpus / "manifest.json").read_text())
        before = self.snapshot()
        for mutation in ("missing_page", "duplicate_page", "wrong_hash", "wrong_geometry", "path_escape", "wrong_owner_document"):
            data = json.loads(json.dumps(original))
            if mutation == "missing_page": data["pages"].pop()
            if mutation == "duplicate_page": data["pages"].append(data["pages"][0])
            if mutation == "wrong_hash": data["pages"][0]["image_sha256"] = "0" * 64
            if mutation == "wrong_geometry": data["pages"][0]["width"] += 1
            if mutation == "path_escape": data["documents"][0]["pdf_path"] = "../outside.pdf"
            if mutation == "wrong_owner_document": data["documents"][0]["sha256"] = "0" * 64
            (corpus / "manifest.json").write_text(json.dumps(data))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                seed(self.engine, self.passwords.__getitem__, corpus / "manifest.json")
            self.assertEqual(before, self.snapshot())

    def test_sql_constraints_reject_invalid_identity(self):
        self.populate()
        statements = [
            "UPDATE documents SET owner_id='no-user'",
            "UPDATE users SET role='root' WHERE username='A'",
            "UPDATE users SET username='a' WHERE username='B'",
            "UPDATE pages SET page_index=-1",
            "UPDATE pages SET width_px=0",
            "UPDATE pages SET page_index=0 WHERE page_index=1",
            "UPDATE documents SET active_version_id=(SELECT v.id FROM document_versions v WHERE v.document_id != documents.id LIMIT 1)",
        ]
        before = self.snapshot()
        for sql in statements:
            with self.subTest(sql=sql), self.assertRaises(IntegrityError):
                with self.engine.begin() as c:
                    c.execute(text(sql))
            self.assertEqual(before, self.snapshot())

    def test_password_failure_does_not_leave_partial_accounts(self):
        before = self.snapshot()
        def provider(name):
            return self.passwords[name] if name == "admin" else "short"
        with self.assertRaisesRegex(ValueError, "12"):
            seed(self.engine, provider)
        self.assertEqual(before, self.snapshot())

    def test_concurrent_initializers_create_only_one_identity_set(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.populate(), range(2)))
        self.assertEqual(sum(r["users"] for r in results), 3)
        self.assertEqual(sum(r["pages"] for r in results), 13)

    def test_cli_generated_credentials_are_local_and_never_reset(self):
        credentials_path = self.base / "credentials.json"
        command = [sys.executable, "-m", "scripts.initialize_database", "--database", str(self.path),
                   "--generate-credentials", str(credentials_path)]
        first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        values = json.loads(credentials_path.read_text())
        before = self.snapshot()
        credential_bytes = credentials_path.read_bytes()
        second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(credentials_path.read_bytes(), credential_bytes)
        with Session(self.engine) as session:
            for user in session.scalars(select(User)):
                self.assertTrue(password_hasher.verify(values[user.username], user.password_hash))
                self.assertNotIn(values[user.username], first.stdout + first.stderr + second.stdout + second.stderr)
        self.assertTrue(all(n == 0 for n in json.loads(second.stdout)["created"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
