"""Real SQLite concurrency/authorization; vector and identity doubles are explicit."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.auth.accounts import change_account
from backend.db.models import Document, IndexEvent, IndexGeneration, IndexOperation, IndexPage, PipelineProfile, SystemState, User
from backend.indexes import service
from backend.search.qdrant import SearchUnavailable
from backend.search.scope import active_index, index_epoch
from tests import test_search as search_tests
from tests.test_ingestion import MemoryQdrant


def identity(expected):
    return dict(encoder_sha256=expected, verified_files=13, implementation_count=2, network_attempts=0, inference_count=0)


class IndexManagementTests(unittest.TestCase):
    setUp = search_tests.SearchTests.setUp
    tearDown = search_tests.SearchTests.tearDown
    login = search_tests.SearchTests.login
    status = search_tests.SearchTests.status

    def setup_management(self):
        self.q = MemoryQdrant(self.engine)
        self.q.collections = deepcopy(self.q.collections)
        self.app.state.qdrant = self.q
        data = self.login('admin')
        self.headers = {'Origin':'http://127.0.0.1:3000', 'X-CSRF-Token':data['csrf_token']}
        self.patch = patch('backend.indexes.service.verify_encoder', side_effect=identity)
        self.patch.start(); self.addCleanup(self.patch.stop)
        with Session(self.engine) as db:
            self.original = active_index(db)[0].id
        self.epoch = 1

    def command(self, index_id=None, **kw):
        return {'request_id':str(uuid4()),'index_id':index_id or self.original,
            'active_index_id':self.original,'index_epoch':self.epoch,'confirmed':True, **kw}

    def post(self, kind, body=None):
        return self.client.post('/admin/index-management/'+kind, json=body or self.command(), headers=self.headers)

    def pointer(self):
        with Session(self.engine) as db:
            return active_index(db)[0].id, index_epoch(db)

    def rebuild(self):
        result=self.post('rebuild');self.status(result,200)
        return result.json()['target_id']

    def test_complete_validate_rebuild_switch_rollback_costs_and_audit(self):
        self.setup_management()
        self.status(self.post('verify'),200)
        candidate=self.rebuild();self.assertEqual(self.pointer(),(self.original,1))
        result=self.post('activate',self.command(candidate));self.status(result,200)
        self.assertEqual(self.pointer(),(candidate,2))
        metrics=result.json()['metrics'];self.assertEqual(metrics['full_bf16_bytes'],13*1031*128*2)
        self.assertEqual(metrics['page_encoding_count'],0)
        result=self.post('activate',self.command(active_index_id=candidate,index_epoch=2));self.status(result,200)
        self.assertEqual(self.pointer(),(self.original,3))
        events=self.client.get('/admin/events?category=index').json()['items'];self.assertTrue(events)
        self.assertTrue({'started','success'}.issubset({r['outcome'] for r in events}))
        self.assertEqual(self.client.get('/admin/tasks?kind=index').json()['items'][0]['kind'],'index')
        self.assertEqual(self.encoder.calls,0)

    def test_auth_changed_password_csrf_origin_and_strict_input(self):
        self.setup_management();self.login('A')
        self.status(self.client.get('/admin/index-management'),403)
        self.status(self.post('rebuild'),403)
        data=self.login('admin');self.headers['X-CSRF-Token']=data['csrf_token']
        for body in (self.command(confirmed=False), self.command(index_epoch=True),self.command(config={}),self.command(index_epoch=0)):
            self.status(self.post('rebuild',body),422)
        for h in ({'Origin':'http://127.0.0.1:3000'},{**self.headers,'Origin':'http://foreign.invalid'}):
            self.status(self.client.post('/admin/index-management/rebuild',json=self.command(),headers=h),403)
        with self.engine.begin() as c:c.execute(update(User).where(User.username=='admin').values(must_change_password=True))
        self.status(self.client.get('/admin/index-management'),403)
        self.assertEqual(self.q.writes,0)

    def test_immutable_profile_mismatch_rejected_before_remote(self):
        self.setup_management()
        with self.engine.begin() as c:c.execute(update(PipelineProfile).values(config_json='{}'))
        self.status(self.post('rebuild'),503)
        self.assertEqual(self.q.writes,0)
        self.assertFalse(self.client.get('/admin/index-management').json()['profiles'][0]['identity_matches'])

    def test_missing_or_tampered_remote_never_changes_pointer(self):
        self.setup_management()
        with Session(self.engine) as db:collection=db.get(IndexGeneration,self.original).collection_name
        self.q.collections[collection][0]['vector']['original'][0][0]=0.7
        self.status(self.post('rebuild'),503)
        self.assertEqual(self.pointer(),(self.original,1))
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(IndexOperation)).status,'failed')
            self.assertEqual(db.scalar(select(IndexGeneration).where(IndexGeneration.id!=self.original)).status,'failed')

    def test_partial_remote_failure_preserves_source_and_explicit_new_attempt(self):
        self.setup_management();original=deepcopy(self.q.collections);self.q.fail_at=2
        body=self.command();self.status(self.post('rebuild',body),503)
        writes=self.q.writes;r=self.post('rebuild',body);self.status(r,200)
        self.assertEqual(r.json()['status'],'failed');self.assertEqual(self.q.writes,writes)
        self.q.fail_at=None;self.rebuild()
        self.assertEqual(self.pointer(),(self.original,1))
        for key,value in original.items():self.assertEqual(self.q.collections[key],value)

    def test_idempotent_replay_and_changed_request_conflict(self):
        self.setup_management();body=self.command();a=self.post('rebuild',body);self.status(a,200)
        writes=self.q.writes;b=self.post('rebuild',body);self.assertEqual(a.json(),b.json());self.assertEqual(self.q.writes,writes)
        self.status(self.post('activate',body),409)

    def test_stale_activate_and_noop_do_not_increment_epoch(self):
        self.setup_management();candidate=self.rebuild()
        self.status(self.post('activate'),200);self.assertEqual(self.pointer(),(self.original,1))
        self.status(self.post('activate',self.command(candidate,index_epoch=2)),409)
        self.status(self.post('activate',self.command(candidate)),200)
        self.status(self.post('activate',self.command()),409)
        self.assertEqual(self.pointer(),(candidate,2))

    def test_rollback_rejects_missing_current_page(self):
        self.setup_management();candidate=self.rebuild()
        self.status(self.post('activate',self.command(candidate)),200)
        with Session(self.engine) as db,db.begin():
            member=db.scalar(select(IndexPage).where(IndexPage.index_id==self.original));db.delete(member)
            index=db.get(IndexGeneration,self.original);index.page_count-=1;index.vector_count-=1031
        self.status(self.post('activate',self.command(active_index_id=candidate,index_epoch=2)),409)
        self.assertEqual(self.pointer(),(candidate,2))

    def test_corpus_tombstone_during_remote_work_discards_candidate(self):
        self.setup_management()
        def tombstone():
            self.q.callback=None
            with self.engine.begin() as c:c.execute(update(Document).where(Document.owner_id==select(User.id).where(User.username=='A').scalar_subquery()).values(status='deleted'))
        self.q.callback=tombstone
        self.status(self.post('rebuild'),409);self.assertEqual(self.pointer(),(self.original,1))

    def test_active_aba_during_rebuild_is_rejected(self):
        self.setup_management()
        def aba():
            self.q.callback=None
            with self.engine.begin() as c:c.execute(update(SystemState).values(active_index_id=self.original,index_epoch=3))
        self.q.callback=aba
        self.status(self.post('rebuild'),409);self.assertEqual(self.pointer(),(self.original,3))

    def test_revocation_during_validation_rechecked_under_final_lock(self):
        self.setup_management()
        def revoke(expected):
            change_account(self.engine,'admin','revoke',self.app.state.clock());return identity(expected)
        self.patch.side_effect=revoke
        with patch('backend.indexes.service.verify_encoder',side_effect=revoke):self.status(self.post('rebuild'),401)
        self.assertEqual(self.pointer(),(self.original,1))

    def test_two_connections_only_one_rebuild_reserved_and_inflight_replay(self):
        self.setup_management();entered=threading.Event();release=threading.Event();body=self.command()
        def verify(expected):
            entered.set();self.assertTrue(release.wait(10));return identity(expected)
        with patch('backend.indexes.service.verify_encoder',side_effect=verify),ThreadPoolExecutor(max_workers=1) as pool:
            first=pool.submit(self.post,'rebuild',body);self.assertTrue(entered.wait(10))
            try:
                self.status(self.post('rebuild'),409)
                replay=self.post('rebuild',body);self.status(replay,200);self.assertEqual(replay.json()['status'],'running')
            finally:release.set()
            self.status(first.result(20),200)
        self.assertEqual(len(self.q.collections),2)

    def test_success_event_failure_rolls_back_activation(self):
        self.setup_management();candidate=self.rebuild();original_event=service.event
        def broken(db,row,outcome,code,clock):
            if outcome=='success':raise RuntimeError('test event failure')
            return original_event(db,row,outcome,code,clock)
        with patch('backend.indexes.service.event',side_effect=broken):self.status(self.post('activate',self.command(candidate)),503)
        self.assertEqual(self.pointer(),(self.original,1))

    def test_concurrent_switches_cannot_overwrite_winning_pointer(self):
        self.setup_management();candidate=self.rebuild();entered=threading.Event();release=threading.Event()
        def verify(expected):
            entered.set();self.assertTrue(release.wait(10));return identity(expected)
        with patch('backend.indexes.service.verify_encoder',side_effect=verify),ThreadPoolExecutor(max_workers=1) as pool:
            first=pool.submit(self.post,'activate',self.command(candidate));self.assertTrue(entered.wait(10))
            try:self.status(self.post('activate',self.command(candidate)),409)
            finally:release.set()
            self.status(first.result(20),200)
        self.assertEqual(self.pointer(),(candidate,2))
        self.status(self.post('activate',self.command()),409)

    def test_identity_verification_failure_never_writes_remote_or_demotes_old(self):
        self.setup_management()
        with patch('backend.indexes.service.verify_encoder',side_effect=SearchUnavailable()):self.status(self.post('rebuild'),503)
        self.assertEqual(self.q.writes,0);self.assertEqual(self.pointer(),(self.original,1))
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(IndexOperation)).status,'failed')

    def test_restart_marks_reserved_operation_interrupted_without_retry(self):
        self.setup_management();candidate=self.rebuild()
        with Session(self.engine) as db,db.begin():
            row=db.scalar(select(IndexOperation));row.status='running'
            db.get(IndexGeneration,candidate).status='building'
        service.recover(self.engine);service.recover(self.engine)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(IndexOperation)).status,'interrupted')
            self.assertEqual(db.get(IndexGeneration,candidate).status,'failed')
        self.assertEqual(self.pointer(),(self.original,1))

    def test_search_rejects_index_epoch_aba(self):
        self.setup_management();self.app.state.qdrant=self.vectorstore;self.login('A')
        def aba():
            with self.engine.begin() as c:c.execute(update(SystemState).values(active_index_id=self.original,index_epoch=3))
        self.encoder.callback=aba
        self.status(self.client.get('/search?q=epoch+test'),409)

    def test_pagination_no_content_paths_or_collection_names(self):
        self.setup_management()
        for _ in range(11):self.status(self.post('verify'),200)
        first=self.client.get('/admin/index-management').json();last=self.client.get('/admin/index-management?operation_offset=10').json()
        self.assertEqual(len(first['operations']),10);self.assertEqual(len(last['operations']),1)
        raw=str(first);self.assertNotIn('collection_name',raw);self.assertNotIn('config_json',raw);self.assertNotIn('password',raw)
        self.status(self.client.get('/admin/index-management?offset=1&offset=2'),422)
