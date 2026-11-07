"""R16 real SQLite authorization/Unicode/cursor tests; explicit encoder/vector doubles."""
from copy import deepcopy
from unittest.mock import patch
import unittest
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.db.models import Document, DocumentVersion, IndexGeneration, IndexPage, Job, Page, User, new_id
from backend.documents.names import normalize_name
from backend.documents import listing
from backend.search.qdrant import Qdrant, SearchUnavailable
from backend.search.scope import allowed_scope
from tests import test_search as base


class SelectionTests(unittest.TestCase):
    setUp = base.SearchTests.setUp
    tearDown = base.SearchTests.tearDown
    login = base.SearchTests.login
    status = base.SearchTests.status
    search = base.SearchTests.search

    def add_document(self, name="同名.pdf", owner="A", ready=False, visibility="private", job_status="queued"):
        with Session(self.engine) as db, db.begin():
            user = db.scalar(select(User).where(User.username == owner))
            original = db.scalar(select(DocumentVersion))
            original_page = db.scalar(select(Page))
            doc = Document(source_key="selection:" + str(uuid4()), owner_id=user.id, display_name=name,
                           visibility=visibility, status="ready" if ready else "registered")
            db.add(doc); db.flush()
            version = DocumentVersion(document_id=doc.id, version=1, pdf_sha256=original.pdf_sha256,
                pdf_path=original.pdf_path, page_count=1, render_profile_json=original.render_profile_json,
                render_profile_sha256=original.render_profile_sha256)
            db.add(version); db.flush()
            if ready:
                doc.active_version_id = version.id
                page = Page(document_version_id=version.id, source_page_id="selection:" + version.id,
                    page_index=0, width_px=original_page.width_px, height_px=original_page.height_px,
                    render_sha256=original_page.render_sha256, image_path=original_page.image_path)
                db.add(page); db.flush()
                index = db.scalar(select(IndexGeneration))
                index.page_count += 1; index.vector_count += 1031
                db.add(IndexPage(index_id=index.id, page_id=page.id, embedding_sha256="d"*64, token_count=1031))
            else:
                db.add(Job(owner_id=user.id, document_version_id=version.id, upload_key=str(uuid4()),
                    request_sha256="e"*64, upload_bytes=100, status=job_status, stage="queued",
                    error_code="PAGE_ENCODING_FAILED" if job_status == "failed" else None))
            return doc.id

    def listing(self, **params):
        return self.client.get("/documents", params=params)

    def test_list_auth_password_and_parameter_boundaries(self):
        self.status(self.listing(), 401)
        self.login()
        with self.engine.begin() as c:
            c.execute(update(User).where(User.username == "A").values(must_change_password=True))
        self.status(self.listing(), 403)
        with self.engine.begin() as c:
            c.execute(update(User).where(User.username == "A").values(must_change_password=False))
        for params in ({"limit": 0}, {"limit": 101}, {"name": "x"*256}, {"owner_id": "B"}, {"cursor": ""}, {"cursor": "bad"}):
            self.status(self.listing(**params), 422)
        self.status(self.client.get("/documents?name=a&name=b"), 422)
        self.assertEqual(self.encoder.calls, 0)
        self.assertEqual(self.vectorstore.calls, [])

    def test_literal_unicode_name_filter_and_unchanged_display_name(self):
        names = ["ＡＢＣ中文_100%.pdf", "Straße.pdf", "中文报告.pdf", "另一份.pdf"]
        ids = {name: self.add_document(name) for name in names}
        self.login()
        for term, expected in [("abc", names[0]), ("ａｂｃ", names[0]), ("STRASSE", names[1]),
                               ("报告", names[2]), ("_", names[0]), ("%", names[0])]:
            response = self.listing(name=term)
            self.status(response, 200)
            self.assertEqual([(i["document_id"], i["display_name"]) for i in response.json()["items"]], [(ids[expected], expected)])
        self.assertEqual(self.listing(name="absent").json()["items"], [])
        self.assertEqual(self.listing(name="  ").json(), self.listing().json())
        self.assertEqual(self.encoder.calls, 0)

    def test_own_notready_shared_ready_deleted_and_same_names(self):
        queued = self.add_document(job_status="queued")
        failed = self.add_document(job_status="failed")
        self.add_document(owner="B", ready=True)
        shared = self.add_document(owner="admin", ready=True, visibility="shared")
        self.add_document(owner="admin", ready=False, visibility="shared")
        self.add_document(owner="B", ready=True, visibility="shared")
        deleted = self.add_document()
        with self.engine.begin() as c:
            c.execute(update(Document).where(Document.id == deleted).values(status="deleted"))
        self.login()
        items = {i["document_id"]: i for i in self.listing(name="同名").json()["items"]}
        self.assertEqual(set(items), {queued, failed, shared})
        self.assertEqual(items[queued]["unsearchable_reason"], "DOCUMENT_NOT_READY")
        self.assertEqual(items[failed]["error_code"], "PAGE_ENCODING_FAILED")
        self.assertFalse(items[failed]["searchable"])
        self.assertTrue(items[shared]["searchable"])
        self.assertEqual(items[shared]["access"], "shared")
        self.assertIsNone(items[shared]["job_status"])
        self.login("admin")
        self.assertNotIn(queued, {i["document_id"] for i in self.listing().json()["items"]})

    def test_session_filter_limit_bound_cursor_and_stable_paging(self):
        for _ in range(4): self.add_document()
        self.login()
        seen, cursor = [], None
        while True:
            response = self.listing(limit=2, **({"cursor": cursor} if cursor else {}))
            self.status(response, 200)
            seen.extend(i["document_id"] for i in response.json()["items"])
            cursor = response.json()["next_cursor"]
            if not cursor: break
        self.assertEqual(len(seen), 5)
        self.assertEqual(len(set(seen)), 5)
        cursor = self.listing(limit=1).json()["next_cursor"]
        for params in ({"name": "changed", "limit": 1}, {"limit": 2}):
            self.status(self.listing(cursor=cursor, **params), 422)
        self.status(self.listing(cursor=cursor[:-1] + "!", limit=1), 422)
        self.login("B")
        self.status(self.listing(cursor=cursor, limit=1), 422)
        self.login("A")
        self.status(self.listing(cursor=cursor, limit=1), 422)

    def test_cursor_invalidated_by_authority_and_snapshot_change(self):
        shared = self.add_document(owner="admin", ready=True, visibility="shared")
        self.login()
        cursor = self.listing(limit=1).json()["next_cursor"]
        with self.engine.begin() as c:
            c.execute(update(Document).where(Document.id == shared).values(visibility="private"))
        response = self.listing(limit=1, cursor=cursor)
        self.status(response, 409)
        self.assertEqual(response.json()["detail"], "DOCUMENT_LIST_CHANGED")

    def test_list_rechecks_authority_before_returning(self):
        shared = self.add_document(owner="admin", ready=True, visibility="shared")
        self.login()
        real = listing.list_snapshot
        count = 0
        def revoke(db, user, key):
            nonlocal count
            result = real(db, user, key)
            count += 1
            if count == 1:
                with self.engine.begin() as c:
                    c.execute(update(Document).where(Document.id == shared).values(visibility="private"))
            return result
        with patch.object(listing, "list_snapshot", side_effect=revoke):
            self.status(self.listing(), 409)

    def test_single_document_scope_and_library_are_distinct(self):
        selected = self.add_document(ready=True)
        self.login()
        response = self.search(document_id=selected, k=50)
        self.status(response, 200)
        self.assertEqual(response.json()["search_mode"], "document")
        self.assertEqual(response.json()["document_id"], selected)
        self.assertEqual({i["document_id"] for i in response.json()["items"]}, {selected})
        scope = self.vectorstore.calls[-1]
        self.assertEqual((scope.index_page_count, len(scope.pages), scope.target_document_id), (14, 1, selected))
        response = self.search(k=50)
        self.status(response, 200)
        self.assertEqual(response.json()["search_mode"], "library")
        self.assertIsNone(response.json()["document_id"])
        self.assertEqual(len(response.json()["items"]), 6)

    def test_invalid_unknown_other_user_and_notready_never_fall_back(self):
        queued = self.add_document()
        other = self.add_document(owner="B", ready=True)
        self.login()
        for identifier, status in [("", 422), ("not-a-uuid", 422), (str(uuid4()), 404), (other, 404), (queued, 409)]:
            self.status(self.search(document_id=identifier), status)
        self.status(self.client.get(f"/search?q=x&document_id={queued}&document_id={other}"), 422)
        self.assertEqual(self.encoder.calls, 0)
        self.assertEqual(self.vectorstore.calls, [])

    def test_selected_share_revoke_and_version_change_during_inference(self):
        selected = self.add_document(owner="admin", ready=True, visibility="shared")
        self.login()
        def revoke():
            with self.engine.begin() as c:
                c.execute(update(Document).where(Document.id == selected).values(visibility="private"))
        self.vectorstore.callback = revoke
        self.status(self.search(document_id=selected), 409)
        self.assertEqual(len(self.vectorstore.calls[-1].pages), 1)
        self.vectorstore.callback = None
        self.status(self.search(document_id=selected), 404)
        own = self.add_document(ready=True)
        def change_version():
            with self.engine.begin() as c:
                c.execute(update(Document).where(Document.id == own).values(active_version_id=None))
        self.encoder.callback = change_version
        self.status(self.search(document_id=own), 409)

    def test_bad_index_does_not_make_selected_search_global(self):
        selected = self.add_document(ready=True)
        self.login()
        self.vectorstore.error = SearchUnavailable("explicit dependency failure")
        self.status(self.search(document_id=selected), 503)
        self.assertEqual(len(self.vectorstore.calls[-1].pages), 1)
        self.assertEqual(self.vectorstore.calls[-1].index_page_count, 14)

    def test_qdrant_filtered_page_ids_and_full_collection_count(self):
        selected = self.add_document(ready=True)
        self.login()
        with Session(self.engine) as db:
            scope = allowed_scope(db, db.scalar(select(User).where(User.username == "A")), selected)
        calls = []
        qdrant = Qdrant()
        with patch.object(qdrant, "info", return_value={}), patch.object(qdrant, "check_info") as check, patch.object(qdrant, "request", side_effect=lambda m,p,b: calls.append(b) or {"points": []}):
            qdrant.query(scope, [[1.0]+[0.0]*127], 3)
        check.assert_called_once_with({}, 14)
        must = calls[0]["filter"]["must"]
        self.assertEqual(next(x["has_id"] for x in must if "has_id" in x), [p.id for p in scope.pages])
        self.assertEqual(len(scope.pages), 1)
        self.assertEqual(calls[0]["params"], {"exact": True})

    def test_rename_normalizes_and_incomplete_pages_not_searchable(self):
        selected = self.add_document(ready=True)
        with Session(self.engine) as db, db.begin():
            doc = db.get(Document, selected)
            doc.display_name = "ＮＥＷ名字.pdf"
            db.execute(IndexPage.__table__.delete().where(IndexPage.page_id.in_(select(Page.id).where(Page.document_version_id == doc.active_version_id))))
        self.login()
        item = self.listing(name="new名字").json()["items"][0]
        self.assertEqual(item["document_id"], selected)
        self.assertFalse(item["searchable"])
        self.assertEqual(item["unsearchable_reason"], "INDEX_INCOMPLETE")
        self.status(self.search(document_id=selected), 503)
