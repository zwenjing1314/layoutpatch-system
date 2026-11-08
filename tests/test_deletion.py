"""Real cookies/migrated SQLite/files; vector/model doubles only in these tests."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.accounts import change_account
from backend.db.connection import ROOT
from backend.db.models import (Document, DocumentCleanup, DocumentVersion, DeletionEvent, IndexGeneration, IndexPage,
                               Job, Page, PageFeature, PageParse, ParsingTask, User, new_id)
from backend.documents.cleanup import CleanupRunner, CleanupSettings, recover_cleanup
from backend.documents.deletion import delete_document
from backend.documents.lifecycle import producing
from backend.documents.routes import read_verified_image
from backend.search.qdrant import Qdrant, SearchUnavailable
from tests import test_region_routes as fixture


class CleanupVectors:
    def __init__(self, db):
        self.points = {}
        self.fail_after_delete = False
        for index in db.scalars(select(IndexGeneration)):
            data = []
            for page in db.scalars(select(Page).join(IndexPage).where(IndexPage.index_id == index.id)):
                version = db.get(DocumentVersion, page.document_version_id)
                data.append({'id': page.id, 'payload': {'document_id': version.document_id, 'document_version_id': version.id}, 'vector': {'original': [[1]]}})
            self.points[index.collection_name] = data
    def info(self, collection): return {'points_count': len(self.points[collection])} if collection in self.points else None
    def check_info(self, info, count=None): pass
    def create(self, collection): self.points[collection] = []
    def all_points(self, collection): return deepcopy(self.points[collection])
    def delete_points(self, collection, ids):
        self.points[collection] = [p for p in self.points[collection] if p['id'] not in ids]
        if self.fail_after_delete:
            self.fail_after_delete = False
            raise SearchUnavailable('Explicit transport uncertainty after remote commit')


class DeletionTests(unittest.TestCase):
    login = fixture.RegionRoutes.login
    change = fixture.RegionRoutes.change

    def setUp(self):
        fixture.RegionRoutes.setUp(self)
        self.files = tempfile.TemporaryDirectory(dir=ROOT/'runtime/corpus/ingest', prefix='deletion-test-')
        self.base = Path(self.files.name)
        self.addCleanup(self.files.cleanup)
        self.settings = CleanupSettings(roots=(self.base,), ingest_root=self.base/'ingest', parsing_root=self.base/'parsing', cache_root=self.base/'cache')
        self.app.state.cleanup.settings = self.settings
        with Session(self.engine) as db, db.begin():
            doc = db.get(Document, self.doc)
            self.version = doc.active_version_id
            version = db.get(DocumentVersion, self.version)
            folder = self.base/self.doc
            folder.mkdir()
            (folder/'source.pdf').write_bytes(b'explicit test PDF content')
            version.pdf_path = (folder/'source.pdf').relative_to(ROOT).as_posix()
            for p in db.scalars(select(Page).where(Page.document_version_id == self.version)):
                target = folder/(p.id+'.png')
                shutil.copyfile(ROOT/p.image_path, target)
                p.image_path = target.relative_to(ROOT).as_posix()
            feature = db.get(PageFeature, self.page)
            for key, name in [('tensor_path', 'full.pt'), ('export_path', 'full.json')]:
                (folder/name).write_bytes(b'explicit test feature double')
                setattr(feature, key, (folder/name).relative_to(ROOT).as_posix())
            other = db.scalar(select(Document).where(Document.id != self.doc))
            other.display_name = doc.display_name
            self.other_doc = other.id
            self.other_version = other.active_version_id
            self.other_owner = other.owner_id
            self.q = CleanupVectors(db)
        self.runner = CleanupRunner(self.engine, self.q, self.settings)
        parser_dir = self.settings.parsing_root/self.task
        parser_dir.mkdir(parents=True)
        (parser_dir/'raw.json').write_text('explicit test raw parser content')
        for key, document_id, version in [('own', self.doc, self.version), ('other', self.other_doc, self.other_version)]:
            folder = self.settings.cache_root/key
            folder.mkdir(parents=True)
            (folder/'manifest.json').write_text(json.dumps({'identity': {'inputs': {'document_id': document_id, 'document_version_id': version}}}))
            (folder/'patches.pt').write_bytes(key.encode())
        self.original_body = self.body()

    def tearDown(self):
        fixture.RegionRoutes.tearDown(self)

    def body(self):
        with Session(self.engine) as db:
            d = db.get(Document, self.doc)
            return {'document_version_id': d.active_version_id, 'access_version': d.access_version, 'confirmed': True}

    def delete(self, body=None, client=None, headers=None, doc=None):
        return (client or self.client).post('/documents/'+(doc or self.doc)+'/delete', json=self.body() if body is None else body,
            headers=self.headers if headers is None else headers)

    def retry(self, attempt=1):
        return self.client.post('/documents/'+self.doc+'/cleanup/retry', json={'attempt': attempt, 'confirmed': True}, headers=self.headers)

    def state(self):
        return self.client.get('/documents/'+self.doc+'/cleanup').json()

    def hidden(self):
        self.assertEqual(self.client.get('/search', params={'q': 'deleted', 'document_id': self.doc}).status_code, 404)
        self.assertEqual(self.client.get('/documents/'+self.doc).status_code, 404)
        self.assertEqual(self.client.get(self.url+'/status').status_code, 404)
        self.assertEqual(self.client.post(self.url, json=self.action, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post('/documents/'+self.doc+'/parsing', json={}, headers=self.headers).status_code, 404)
        self.assertNotIn(self.doc, [i['document_id'] for i in self.client.get('/documents').json()['items']])

    def test_permissions_first_change_origin_csrf_owner_admin_and_strict_inputs(self):
        self.assertEqual(self.delete(headers={}).status_code, 403)
        self.assertEqual(self.delete(headers={**self.headers, 'X-CSRF-Token': 'wrong'}).status_code, 403)
        for update in ({'confirmed': False}, {'confirmed': 'true'}, {'access_version': True}, {'access_version': 0}, {'owner_id': self.owner}):
            self.assertEqual(self.delete(body={**self.body(), **update}).status_code, 422)
        for query in ('?scope=all', '?limit=1&limit=2'):
            self.assertEqual(self.client.get('/documents/deletion'+query).status_code, 422)
        self.assertEqual(self.client.get('/documents/deletion').status_code, 200)
        self.assertEqual(self.delete(doc=self.other_doc).status_code, 404)
        for name in ('B', 'admin'):
            self.login(name)
            self.headers['X-CSRF-Token'] = self.client.get('/auth/me').json()['csrf_token']
            self.assertEqual(self.delete(body=self.original_body).status_code, 404)
            self.assertEqual(self.client.get('/documents/'+self.doc+'/cleanup').status_code, 404)
            self.assertEqual(self.retry().status_code, 404)
        self.login('A'); self.headers['X-CSRF-Token'] = self.client.get('/auth/me').json()['csrf_token']
        self.change(User, self.owner, must_change_password=True)
        self.assertEqual(self.delete().status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self.delete(body=self.original_body).status_code, 401)

    def test_atomic_tombstone_event_failure_and_stale_input(self):
        self.assertEqual(self.delete(body={**self.body(), 'access_version': 9}).status_code, 409)
        with self.engine.begin() as c:
            c.exec_driver_sql("CREATE TRIGGER fail_deletion BEFORE INSERT ON deletion_events WHEN NEW.outcome='success' BEGIN SELECT RAISE(ABORT,'explicit test'); END")
        self.assertEqual(self.delete().status_code, 503)
        with Session(self.engine) as db:
            self.assertEqual(db.get(Document, self.doc).status, 'ready')
            self.assertIsNone(db.scalar(select(DocumentCleanup)))

    def test_immediate_hidden_old_links_and_exact_replay_even_after_completion(self):
        hit = self.client.get('/search', params={'q': 'before', 'document_id': self.doc}).json()['items'][0]
        crop = self.client.post(self.url, json=self.action, headers=self.headers).json()['items'][0]['crop_url']
        self.assertEqual(self.delete().status_code, 202)
        self.hidden()
        for link in (hit['preview_url'], crop): self.assertEqual(self.client.get(link).status_code, 404)
        self.assertEqual(self.delete(body=self.original_body).status_code, 202)
        self.runner.run_one()
        self.assertEqual(self.state()['cleanup_status'], 'completed')
        self.assertEqual(self.delete(body=self.original_body).status_code, 202)
        self.assertEqual(self.state()['access_version'], 2)
        self.assertEqual(self.retry().status_code, 202)
        self.assertFalse(self.runner.run_one())

    def test_cleanup_all_owned_artifacts_rows_and_preserves_same_name_other_user(self):
        self.delete(); self.assertTrue(self.runner.run_one())
        self.assertEqual(self.state()['cleanup_status'], 'completed')
        self.assertFalse((self.base/self.doc).exists())
        self.assertFalse((self.settings.parsing_root/self.task).exists())
        self.assertFalse((self.settings.cache_root/'own').exists())
        self.assertTrue((self.settings.cache_root/'other/patches.pt').exists())
        with Session(self.engine) as db:
            self.assertIsNone(db.get(DocumentVersion, self.version))
            self.assertIsNone(db.get(Page, self.page))
            self.assertIsNone(db.get(PageFeature, self.page))
            self.assertIsNone(db.get(PageParse, (self.task, self.page)))
            self.assertIsNone(db.get(ParsingTask, self.task))
            self.assertEqual(db.get(Document, self.other_doc).status, 'ready')
            self.assertNotIn('files', json.loads(db.scalar(select(DocumentCleanup)).manifest_json))
            index = db.scalar(select(IndexGeneration))
            self.assertEqual((index.page_count, index.vector_count), (8, 8*1031))
            self.assertEqual(len(list(db.scalars(select(IndexPage)))), 8)
        self.login('B')
        self.assertEqual(self.client.get('/search', params={'q': 'survivor', 'document_id': self.other_doc}).status_code, 200)

    def test_file_failure_remains_unreadable_then_retry_idempotent_and_stale_attempt(self):
        self.delete()
        with patch('backend.documents.cleanup.remove_paths', side_effect=PermissionError('explicit locked file')):
            self.runner.run_one()
        self.assertEqual((self.state()['cleanup_status'], self.state()['error_code']), ('failed', 'CLEANUP_STORAGE_FAILED'))
        self.hidden()
        self.assertEqual(self.retry().status_code, 202)
        self.assertEqual(self.retry().status_code, 409)
        self.assertEqual(self.retry(2).status_code, 202)
        self.runner.run_one()
        self.assertEqual((self.state()['cleanup_status'], self.state()['attempt']), ('completed', 2))

    def test_remote_delete_uncertainty_reconciles_after_restart(self):
        self.delete(); self.q.fail_after_delete = True; self.runner.run_one()
        self.assertEqual(self.state()['error_code'], 'CLEANUP_INDEX_UNAVAILABLE')
        self.hidden(); self.retry()
        with Session(self.engine) as db, db.begin():
            db.scalar(select(DocumentCleanup)).status = 'running'
        recover_cleanup(self.engine)
        self.runner.run_one()
        self.assertEqual(self.state()['cleanup_status'], 'completed')

    def test_existing_writer_does_not_delay_tombstone_cleanup_waits_no_recreated_residuals(self):
        entered, release = threading.Event(), threading.Event()
        def writer():
            with producing(self.engine):
                entered.set(); self.assertTrue(release.wait(5))
                (self.base/self.doc/'late.txt').write_bytes(b'late writer output')
        with ThreadPoolExecutor(max_workers=1) as pool:
            f = pool.submit(writer); self.assertTrue(entered.wait(5))
            self.assertEqual(self.delete().status_code, 202); self.hidden()
            self.assertFalse(self.runner.run_one())
            release.set(); f.result(5)
        self.runner.run_one()
        self.assertEqual(self.state()['cleanup_status'], 'completed')
        self.assertFalse((self.base/self.doc).exists())

    def test_region_inflight_no_return_and_cache_cannot_be_published_after_cleanup(self):
        def deleting():
            self.assertEqual(self.delete().status_code, 202)
            self.assertFalse(self.runner.run_one())
        self.region_worker.callback = deleting
        self.assertEqual(self.client.post(self.url, json=self.action, headers=self.headers).status_code, 404)
        self.runner.run_one(); self.assertEqual(self.state()['cleanup_status'], 'completed')

    def test_PNG_and_search_inflight_refuse_after_tombstone(self):
        hit = self.client.get('/search', params={'q': 'image', 'document_id': self.doc}).json()['items'][0]
        def read(page):
            data = read_verified_image(page); self.delete(); return data
        with patch('backend.documents.routes.read_verified_image', read):
            self.assertEqual(self.client.get(hit['preview_url']).status_code, 404)

    def test_shared_physical_reference_blocks_before_any_index_or_file_removal(self):
        with Session(self.engine) as db, db.begin():
            db.get(DocumentVersion, self.other_version).pdf_path = db.get(DocumentVersion, self.version).pdf_path
        original = deepcopy(self.q.points)
        self.delete(); self.runner.run_one()
        self.assertEqual(self.state()['error_code'], 'CLEANUP_REFERENCED_FILE')
        self.assertEqual(self.q.points, original)
        self.assertTrue((self.base/self.doc/'source.pdf').exists())

    def test_outside_root_or_parent_traversal_is_rejected_before_side_effects(self):
        self.change(DocumentVersion, self.version, pdf_path='../layoutpatch/source.pdf')
        original = deepcopy(self.q.points); self.delete(); self.runner.run_one()
        self.assertEqual(self.state()['error_code'], 'CLEANUP_PATH_INVALID')
        self.assertEqual(self.q.points, original)

    def test_unknown_cache_temporary_is_preserved_and_blocks_completion(self):
        folder = self.settings.cache_root/'tmp-unattributable'
        folder.mkdir(); (folder/'patches.pt').write_bytes(b'unknown owner')
        self.delete(); self.runner.run_one()
        self.assertEqual(self.state()['error_code'], 'CLEANUP_CACHE_UNATTRIBUTED')
        self.assertTrue(folder.exists())

    def test_symlink_is_rejected_without_touching_target(self):
        target = self.base/'must-retain.txt'; target.write_text('retain')
        link = self.base/self.doc/'linked.txt'
        try: link.symlink_to(target)
        except OSError as e: self.skipTest('Local OS does not allow creating symlink: '+str(e.winerror))
        self.delete(); self.runner.run_one()
        self.assertEqual(self.state()['error_code'], 'CLEANUP_PATH_INVALID')
        self.assertEqual(target.read_text(), 'retain')

    @unittest.skipUnless(os.name == 'nt', 'Windows junction boundary')
    def test_Windows_junction_is_rejected_without_following_it(self):
        target = self.base/'junction-target'; target.mkdir(); (target/'retain.txt').write_text('retain')
        link = self.base/self.doc/'junction'
        subprocess.run(['powershell', '-NoProfile', '-Command', f"New-Item -ItemType Junction -Path '{link}' -Target '{target}' | Out-Null"], check=True, capture_output=True)
        try:
            self.delete(); self.runner.run_one()
            self.assertEqual(self.state()['error_code'], 'CLEANUP_PATH_INVALID')
            self.assertEqual((target/'retain.txt').read_text(), 'retain')
        finally:
            link.rmdir()

    def test_unowned_collection_prefix_fails_without_remote_mutation(self):
        self.runner.settings = CleanupSettings(roots=(self.base,), ingest_root=self.settings.ingest_root,
            parsing_root=self.settings.parsing_root, cache_root=self.settings.cache_root, collection_prefix='layoutpatch_system_owned_')
        before = deepcopy(self.q.points); self.delete(); self.runner.run_one()
        self.assertEqual(self.state()['error_code'], 'CLEANUP_COLLECTION_NOT_OWNED'); self.assertEqual(self.q.points, before)

    def test_failed_candidate_generation_without_membership_is_also_cleaned(self):
        with Session(self.engine) as db, db.begin():
            original = db.scalar(select(IndexGeneration))
            index = IndexGeneration(profile_id=original.profile_id, collection_name='layoutpatch_system_failed_test', status='failed')
            db.add(index)
            self.q.points[index.collection_name] = [{'id': new_id(), 'payload': {'document_id': self.doc, 'document_version_id': self.version}, 'vector': {'original': [[1]]}}]
        self.delete(); self.runner.run_one()
        self.assertEqual(self.state()['cleanup_status'], 'completed')
        self.assertEqual(self.q.points['layoutpatch_system_failed_test'], [])

    def test_two_connections_delete_same_input_commit_once_and_noop(self):
        other = TestClient(self.app); self.addCleanup(other.close)
        r = other.post('/auth/login', json={'username': 'A', 'password': self.passwords['A']}, headers={'Origin': fixture.ORIGIN})
        h = {'Origin': fixture.ORIGIN, 'X-CSRF-Token': r.json()['csrf_token']}; barrier = threading.Barrier(2)
        def run(client, headers):
            barrier.wait(5); return self.delete(body=self.original_body, client=client, headers=headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(run, self.client, self.headers), pool.submit(run, other, h)
            self.assertEqual([a.result(10), b.result(10)], [202, 202])
        with Session(self.engine) as db:
            self.assertCountEqual(list(db.scalars(select(DeletionEvent.outcome))), ['success', 'noop'])
            self.assertEqual(len(list(db.scalars(select(DocumentCleanup)))), 1)

    def test_cookie_loaded_then_revoked_before_write_lock_is_refused(self):
        entered, release = threading.Event(), threading.Event()
        def wait(*args, **kwargs):
            entered.set(); self.assertTrue(release.wait(5)); return delete_document(*args, **kwargs)
        with patch('backend.documents.deletion.delete_document', wait), ThreadPoolExecutor(max_workers=1) as pool:
            f = pool.submit(self.delete); self.assertTrue(entered.wait(5))
            change_account(self.engine, 'A', 'revoke', 1794110400); release.set()
            self.assertEqual(f.result(10).status_code, 401)
        with Session(self.engine) as db: self.assertIsNone(db.scalar(select(DocumentCleanup)))

    def test_publish_delete_race_serializes_and_never_restores_a_tombstone(self):
        self.change(User, self.owner, role='admin')
        other = TestClient(self.app); self.addCleanup(other.close)
        r = other.post('/auth/login', json={'username': 'A', 'password': self.passwords['A']}, headers={'Origin': fixture.ORIGIN})
        headers = {'Origin': fixture.ORIGIN, 'X-CSRF-Token': r.json()['csrf_token']}
        body = self.original_body; barrier = threading.Barrier(2)
        def publish():
            barrier.wait(5)
            return other.post('/admin/documents/'+self.doc+'/publish', json=body, headers=headers).status_code
        def deleting():
            barrier.wait(5); return self.delete(body=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(publish), pool.submit(deleting)
            result = (a.result(10), b.result(10))
        self.assertIn(result, ((200, 409), (404, 202)))
        if result[1] == 409: self.assertEqual(self.delete().status_code, 202)
        self.assertEqual(other.post('/admin/documents/'+self.doc+'/publish', json=self.body(), headers=headers).status_code, 404)
        self.hidden()

    def test_qdrant_delete_contract_waits_and_uses_exact_ids(self):
        q = Qdrant()
        with patch.object(q, 'request') as request:
            q.delete_points('layoutpatch_system_test', ['one', 'two'])
            request.assert_called_once_with('POST', '/collections/layoutpatch_system_test/points/delete?wait=true', {'points': ['one', 'two']})

    def test_actual_parser_lease_and_post_parse_authority_prevent_recreation(self):
        from backend.parsing.runner import ParsingRunner
        with Session(self.engine) as db, db.begin():
            task = db.get(ParsingTask, self.task); task.status = 'queued'
            record = db.get(PageParse, (self.task, self.page)); record.status = 'pending'
            candidates = json.loads(record.candidates_json)
        def parser(task_id, version, page, profile):
            self.assertEqual(self.delete().status_code, 202)
            self.assertFalse(self.runner.run_one())
            (self.settings.parsing_root/task_id/'late-parser.json').write_text('late parser output')
            return candidates, {}
        parser_runner = ParsingRunner(self.engine, parser=parser, verifier=lambda _: None)
        parser_runner.run_one()
        self.assertEqual(self.state()['cleanup_status'], 'queued')
        self.runner.run_one(); self.assertEqual(self.state()['cleanup_status'], 'completed')
        self.assertFalse((self.settings.parsing_root/self.task).exists())

    def test_actual_upload_lease_cleans_receiving_write_and_cannot_queue_deleted_document(self):
        from backend.documents.uploads import UploadSettings, write_pdf
        from tests.test_uploads import pdf_bytes
        self.app.state.upload_settings = UploadSettings(root=self.base/'uploads')
        target = {}
        def write(path, data):
            with Session(self.engine) as db:
                doc = db.scalar(select(Document).where(Document.source_key == 'upload:'+path.parent.name))
                target['id'] = doc.id
            body = {'document_version_id': None, 'access_version': 1, 'confirmed': True}
            self.assertEqual(self.delete(doc=target['id'], body=body).status_code, 202)
            self.assertFalse(self.runner.run_one())
            write_pdf(path, data)
        with patch('backend.documents.ingest.write_pdf', write):
            r = self.client.post('/index', files={'file': ('same.pdf', pdf_bytes(), 'application/pdf')},
                headers={**self.headers, 'X-Upload-ID': new_id()})
        self.assertEqual(r.status_code, 404)
        self.runner.run_one()
        with Session(self.engine) as db:
            task = db.scalar(select(DocumentCleanup).where(DocumentCleanup.document_id == target['id']))
            self.assertEqual(task.status, 'completed')
            self.assertIsNone(db.scalar(select(Job).join(DocumentVersion).where(DocumentVersion.document_id == target['id'])))

    def test_actual_ingestion_checkpoint_after_renderer_refuses_deleted_job(self):
        from backend.documents.pipeline import IngestionRunner
        from backend.documents.uploads import UploadSettings
        from tests.test_uploads import pdf_bytes
        from tests.test_ingestion import renderer
        self.app.state.ingestion.close()
        self.app.state.upload_settings = UploadSettings(root=self.base/'uploads')
        r = self.client.post('/index', files={'file': ('same.pdf', pdf_bytes(), 'application/pdf')}, headers={**self.headers, 'X-Upload-ID': new_id()})
        self.assertEqual(r.status_code, 202)
        doc_id, job_id = r.json()['document_id'], r.json()['job_id']
        # Only this generated job directory can be touched by this test runner.
        roots = (*self.settings.roots, ROOT/'runtime/corpus/ingest')
        settings = CleanupSettings(roots=roots, parsing_root=self.settings.parsing_root, cache_root=self.settings.cache_root)
        self.app.state.cleanup.settings = settings
        cleanup = CleanupRunner(self.engine, self.q, settings)
        with Session(self.engine) as db, db.begin():
            original = db.scalar(select(IndexGeneration))
            # These explicit doubles need valid metadata, not real embedding bytes.
            original.page_count = len(self.q.points[original.collection_name])
        def render(worker, version, output):
            self.assertEqual(self.delete(doc=doc_id, body={'document_version_id': None, 'access_version': 1, 'confirmed': True}).status_code, 202)
            self.assertFalse(cleanup.run_one())
            return renderer(worker, version, output)
        worker = IngestionRunner(self.engine, object(), self.q, renderer=render)
        try:
            worker.run_one()
            with Session(self.engine) as db: self.assertEqual(db.get(Job, job_id).status, 'cancelled')
            cleanup.run_one()
            with Session(self.engine) as db: self.assertEqual(db.scalar(select(DocumentCleanup.status).where(DocumentCleanup.document_id == doc_id)), 'completed')
            self.assertFalse((ROOT/'runtime/corpus/ingest'/job_id).exists())
        finally:
            directory = ROOT/'runtime/corpus/ingest'/job_id
            if directory.exists(): shutil.rmtree(directory)
