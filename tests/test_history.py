"""Real migrated SQLite/cookies, explicit inference doubles; no live source writes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.auth.accounts import account_transaction, change_account
from backend.auth.settings import AuthSettings
from backend.db.models import (Document, DocumentVersion, HistoryEvent, IndexPage, Page, PageFeature, PageParse,
    ParsingTask, PipelineProfile, QueryHistory, QueryHistoryHit, QueryRequest, User)
from backend.history.service import recover_history
from backend.main import create_app
from backend.search.qdrant import SearchUnavailable
from tests import test_region_routes as fixture


class HistoryTests(unittest.TestCase):
    login = fixture.RegionRoutes.login
    change = fixture.RegionRoutes.change
    tearDown = fixture.RegionRoutes.tearDown

    def setUp(self):
        fixture.RegionRoutes.setUp(self)

    def body(self, **kw):
        return {'q':'fresh private question', 'k':3, 'request_id':str(uuid4()), **kw}

    def submit(self, body=None, client=None, headers=None):
        return (client or self.client).post('/search', json=body or self.body(), headers=self.headers if headers is None else headers)

    def saved(self, **kw):
        response=self.submit(self.body(**kw)); self.assertEqual(response.status_code,200,response.text)
        return response.json()['history']

    def count(self, model):
        with Session(self.engine) as db:return db.scalar(select(func.count()).select_from(model))

    def new_login(self, name='A'):
        self.login(name); self.headers['X-CSRF-Token']=self.client.get('/auth/me').json()['csrf_token']

    def update(self, history, **kw):
        return self.client.patch('/history/'+history['entry']['history_id'],json={'version':history['entry']['version'],**kw},headers=self.headers)

    def remove(self, history):
        return self.client.request('DELETE','/history/'+history['entry']['history_id'],json={'version':history['entry']['version'],'confirmed':True},headers=self.headers)

    def test_auth_first_change_origin_csrf_and_strict_input(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/history').status_code,401)
        self.assertEqual(self.submit().status_code,401)
        self.new_login()
        for headers in ({},{'Origin':fixture.ORIGIN},{**self.headers,'X-CSRF-Token':'wrong'}):
            self.assertEqual(self.submit(headers=headers).status_code,403)
        for updates in ({'request_id':'bad'},{'q':' '},{'q':'q'*2001},{'q':'q\x00bad'},{'k':True},{'k':'3'},{'k':51},{'owner_id':self.owner},{'items':[]},{'profile_id':'bad'}):
            self.assertEqual(self.submit(self.body(**updates)).status_code,422)
        self.assertEqual(self.client.post('/search?q=x',json=self.body(),headers=self.headers).status_code,422)
        for query in ('?owner=x','?limit=1&limit=2','?offset=-1'):
            self.assertEqual(self.client.get('/history'+query).status_code,422)
        self.change(User,self.owner,must_change_password=True)
        self.assertEqual(self.submit().status_code,403)
        self.assertEqual(self.client.get('/history').status_code,403)
        self.assertEqual(self.encoder.calls,0);self.assertEqual(self.count(QueryRequest),0)

    def test_get_stays_readonly_new_request_ids_really_encode_repeat_question(self):
        r=self.client.get('/search',params={'q':'fresh private question'});self.assertEqual(r.status_code,200)
        self.assertEqual(self.count(QueryHistory),0);self.assertEqual(self.count(QueryRequest),0)
        a=self.saved();b=self.saved()
        self.assertNotEqual(a['entry']['history_id'],b['entry']['history_id'])
        self.assertEqual(self.encoder.calls,3);self.assertEqual(self.count(QueryHistoryHit),6)

    def test_same_key_replay_does_not_encode_and_new_session_reissues_links(self):
        body=self.body(q='  original query  ')
        first=self.submit(body).json();old=first['history']['items'][0]['preview_url']
        self.assertFalse(first['replayed']);self.assertEqual(self.encoder.calls,1)
        self.new_login()
        again=self.submit({**body,'q':'original query'});self.assertEqual(again.status_code,200,again.text)
        self.assertTrue(again.json()['replayed']);self.assertEqual(self.encoder.calls,1)
        fresh=again.json()['history']['items'][0]['preview_url']
        self.assertNotEqual(old,fresh);self.assertEqual(self.client.get(old).status_code,404)
        self.assertEqual(self.client.get(fresh).status_code,200)
        self.assertEqual(self.submit({**body,'q':'different query'}).status_code,409)
        self.assertEqual(self.count(QueryHistory),1)

    def test_owner_isolation_including_admin_and_same_request_key_other_user(self):
        body=self.body();h=self.submit(body).json()['history'];url='/history/'+h['entry']['history_id']
        for name in ('B','admin'):
            self.new_login(name)
            self.assertEqual(self.client.get('/history').json()['items'],[])
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.client.patch(url,json={'version':1,'title':'leak'},headers=self.headers).status_code,404)
            self.assertEqual(self.client.request('DELETE',url,json={'version':1,'confirmed':True},headers=self.headers).status_code,404)
        self.new_login('B');r=self.submit(body)
        self.assertEqual(r.status_code,200);self.assertFalse(r.json()['replayed'])
        self.assertNotEqual(r.json()['history']['entry']['history_id'],h['entry']['history_id'])
        self.assertEqual(self.encoder.calls,2)

    def test_empty_is_saved_without_model_and_failures_never_save_half_history(self):
        self.new_login('admin');h=self.saved()
        self.assertEqual(h['entry']['result_status'],'empty');self.assertEqual(h['items'],[]);self.assertEqual(self.encoder.calls,0)
        self.new_login();body=self.body();self.encoder.error=SearchUnavailable('private exception payload')
        r=self.submit(body);self.assertEqual(r.status_code,503);self.assertNotIn('private exception',r.text)
        self.assertEqual(self.count(QueryHistory),1);self.assertEqual(self.count(QueryHistoryHit),0)
        with Session(self.engine) as db:
            marker=db.scalar(select(QueryRequest).where(QueryRequest.request_key==body['request_id']));self.assertEqual(marker.status,'failed')
        self.encoder.error=None;calls=self.encoder.calls
        self.assertEqual(self.submit(body).status_code,409);self.assertEqual(self.encoder.calls,calls)
        self.saved();self.assertEqual(self.encoder.calls,calls+1)

    def test_metadata_rename_pin_noop_and_original_query_immutable(self):
        h=self.saved(q='original\nquestion');self.assertEqual(h['entry']['original_title'],'original question')
        r=self.update(h,title='新标题',pinned=True);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['version'],2);self.assertIsNotNone(r.json()['pinned_at'])
        self.assertEqual(self.update(h,title='stale').status_code,409)
        h['entry']=r.json();r=self.update(h,title='新标题',pinned=True)
        self.assertEqual(r.json()['version'],2)
        h['entry']=r.json();r=self.update(h,pinned=False);self.assertEqual(r.json()['version'],3);self.assertIsNone(r.json()['pinned_at'])
        d=self.client.get('/history/'+h['entry']['history_id']).json()
        self.assertEqual(d['q'],'original\nquestion');self.assertEqual(d['entry']['original_title'],'original question')
        self.assertEqual(d['entry']['title'],'新标题');self.assertEqual(self.encoder.calls,1)

    def test_metadata_and_delete_schema_reject_injection_null_controls(self):
        h=self.saved();url='/history/'+h['entry']['history_id']
        for updates in ({},{'title':None},{'title':' '},{'title':'x'*101},{'title':'a\nb'},{'title':'a\x00b'},{'pinned':None},{'pinned':'true'},{'version':True,'title':'x'},{'q':'replace'},{'owner_id':self.owner}):
            self.assertEqual(self.client.patch(url,json={'version':1,**updates},headers=self.headers).status_code,422)
        for body in ({'version':1,'confirmed':False},{'version':True,'confirmed':True},{'version':1,'confirmed':'true'},{'version':1,'confirmed':True,'items':[]}):
            self.assertEqual(self.client.request('DELETE',url,json=body,headers=self.headers).status_code,422)
        self.assertEqual(self.client.get(url+'?x=1').status_code,422)
        self.assertEqual(self.client.patch(url+'?x=1',json={'version':1,'title':'x'},headers=self.headers).status_code,422)

    def test_pinned_order_and_tied_timestamp_stable_pagination(self):
        records=[self.saved(q=f'pagination {i}') for i in range(12)]
        with Session(self.engine) as db,db.begin():
            for h in db.scalars(select(QueryHistory)):h.created_at='2026-01-01T00:00:00+00:00'
        oldest=min(records,key=lambda h:h['entry']['history_id']);self.assertEqual(self.update(oldest,pinned=True).status_code,200)
        first=self.client.get('/history').json();second=self.client.get('/history?offset=10').json()
        self.assertEqual((len(first['items']),len(second['items'])),(10,2))
        ids=[i['history_id'] for i in first['items']+second['items']]
        self.assertEqual(ids[0],oldest['entry']['history_id']);self.assertEqual(ids[1:],sorted(ids[1:],reverse=True))
        self.assertEqual(len(set(ids)),12);self.assertIsNone(second['next_offset'])
        self.assertEqual(first['scope_version'],second['scope_version'])

    def test_delete_removes_private_content_hits_and_prevents_request_resurrection(self):
        body=self.body();h=self.submit(body).json()['history'];before=self.count(Document)
        self.assertEqual(self.remove(h).status_code,200)
        self.assertEqual(self.client.get('/history/'+h['entry']['history_id']).status_code,404)
        self.assertEqual(self.count(QueryHistory),0);self.assertEqual(self.count(QueryHistoryHit),0)
        self.assertEqual(self.count(Document),before);self.assertEqual(self.submit(body).status_code,410)
        self.assertEqual(self.encoder.calls,1);self.assertEqual(self.remove(h).status_code,404)
        with Session(self.engine) as db:
            marker=db.scalar(select(QueryRequest));self.assertEqual(marker.status,'deleted')
            for e in db.scalars(select(HistoryEvent)):
                self.assertNotIn(body['q'],str(e.__dict__))
                self.assertNotIn('preview_url',str(e.__dict__))

    def test_open_history_never_runs_query_or_region_and_current_region_still_works(self):
        h=self.saved();self.encoder.error=SearchUnavailable('must never run')
        d=self.client.get('/history/'+h['entry']['history_id']);self.assertEqual(d.status_code,200,d.text)
        self.assertTrue(d.json()['historical']);self.assertEqual(self.encoder.calls,1);self.assertEqual(self.region_worker.calls,0)
        self.assertNotIn('crop_url',d.text);self.assertNotIn('tensor_path',d.text)
        self.assertEqual(self.client.get(d.json()['items'][0]['preview_url']).status_code,200)
        r=self.client.post(self.url,json=self.action,headers=self.headers);self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get(r.json()['items'][0]['crop_url']).status_code,200)

    def share(self):
        with Session(self.engine) as db,db.begin():
            admin=db.scalar(select(User).where(User.username=='admin'))
            d=db.get(Document,self.doc);d.owner_id=admin.id;d.visibility='shared';d.access_version+=1

    def test_withdraw_and_ABA_never_reveal_old_names_ids_or_links(self):
        self.share();h=self.saved(document_id=self.doc);url='/history/'+h['entry']['history_id'];old=h['items'][0]
        self.change(Document,self.doc,visibility='private',access_version=3)
        r=self.client.get(url);self.assertEqual(r.status_code,200,r.text)
        d=r.json();self.assertEqual(d['items'],[]);self.assertEqual(d['unavailable_count'],3)
        self.assertFalse(d['target_available']);self.assertIsNone(d['document_id'])
        for value in (old['page_id'],old['document_name'],old['preview_url']):self.assertNotIn(value,r.text)
        self.change(Document,self.doc,visibility='shared',access_version=4)
        self.assertEqual(self.client.get(url).json()['items'],[])
        self.assertEqual(self.client.get(old['preview_url']).status_code,404)
        fresh=self.saved(document_id=self.doc);self.assertEqual(len(fresh['items']),3)

    def test_history_survives_physical_document_rows_removed_but_never_restores_them(self):
        h=self.saved(document_id=self.doc)
        with Session(self.engine) as db,db.begin():
            d=db.get(Document,self.doc);version=d.active_version_id;d.status='deleted';d.active_version_id=None;d.deleted_at='deleted';d.access_version+=1;db.flush()
            pages=select(Page.id).where(Page.document_version_id==version);tasks=select(ParsingTask.id).where(ParsingTask.document_version_id==version)
            db.execute(delete(PageParse).where(PageParse.task_id.in_(tasks)));db.execute(delete(ParsingTask).where(ParsingTask.document_version_id==version))
            db.execute(delete(PageFeature).where(PageFeature.page_id.in_(pages)));db.execute(delete(IndexPage).where(IndexPage.page_id.in_(pages)))
            db.execute(delete(Page).where(Page.document_version_id==version));db.execute(delete(DocumentVersion).where(DocumentVersion.id==version))
        r=self.client.get('/history/'+h['entry']['history_id']);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['items'],[]);self.assertEqual(r.json()['unavailable_count'],3)
        self.assertEqual(self.count(QueryHistoryHit),3);self.assertEqual(self.encoder.calls,1)

    def test_render_embedding_and_profile_changes_fail_closed(self):
        h=self.saved(document_id=self.doc);url='/history/'+h['entry']['history_id']
        with Session(self.engine) as db,db.begin():
            for ip in db.scalars(select(IndexPage).join(Page).where(Page.document_version_id==h['items'][0]['document_version_id'])):ip.embedding_sha256='d'*64
        self.assertEqual(self.client.get(url).json()['unavailable_count'],3)
        with Session(self.engine) as db,db.begin():
            p=db.scalar(select(PipelineProfile));p.config_sha256='a'*64
        self.assertEqual(self.client.get(url).status_code,503)
        self.assertEqual(self.client.get('/history').status_code,200)

    def test_post_rechecks_revoke_and_document_scope_during_inference(self):
        self.encoder.callback=lambda:change_account(self.engine,'A','revoke',self.app.state.clock())
        self.assertEqual(self.submit().status_code,401);self.assertEqual(self.count(QueryHistory),0)
        self.encoder.callback=None;self.new_login()
        self.vectorstore.callback=lambda:self.change(Document,self.doc,status='deleted')
        self.assertEqual(self.submit().status_code,409);self.assertEqual(self.count(QueryHistory),0)

    def test_detail_rechecks_between_reads_and_never_returns_stale_reference(self):
        h=self.saved();from backend.history.service import detail as original
        calls=[]
        def changing(*args):
            result=original(*args);calls.append(1)
            if len(calls)==1:self.change(Document,self.doc,status='deleted')
            return result
        with patch('backend.history.routes.detail',side_effect=changing):
            r=self.client.get('/history/'+h['entry']['history_id']);self.assertEqual(r.status_code,409,r.text)

    def test_concurrent_identical_request_has_one_forward_and_pending_conflict(self):
        started=threading.Event();release=threading.Event();body=self.body()
        self.encoder.callback=lambda:(started.set(),release.wait(10))
        other=TestClient(self.app);other.cookies.update(self.client.cookies);self.addCleanup(other.close)
        with ThreadPoolExecutor(max_workers=1) as pool:
            first=pool.submit(self.submit,body)
            try:
                self.assertTrue(started.wait(5));second=self.submit(body,client=other)
                self.assertEqual(second.status_code,409,second.text);self.assertEqual(second.json()['detail'],'HISTORY_REQUEST_PENDING')
            finally:release.set()
            self.assertEqual(first.result(timeout=10).status_code,200)
        self.assertEqual(self.encoder.calls,1);self.assertEqual(self.count(QueryHistory),1)
        self.assertTrue(self.submit(body).json()['replayed'])

    def test_two_metadata_writers_same_version_only_one_commits(self):
        h=self.saved();url='/history/'+h['entry']['history_id'];other=TestClient(self.app);other.cookies.update(self.client.cookies);self.addCleanup(other.close)
        def write(client,title):return client.patch(url,json={'version':1,'title':title},headers=self.headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(write,self.client,'one');b=pool.submit(write,other,'two');codes=[a.result(),b.result()]
        self.assertEqual(sorted(codes),[200,409]);self.assertEqual(self.client.get(url).json()['entry']['version'],2)

    def test_cookie_loaded_before_lock_then_revoked_cannot_mutate(self):
        h=self.saved();called=[]
        @contextmanager
        def delayed(engine):
            if not called:called.append(1);change_account(engine,'A','revoke',self.app.state.clock())
            with account_transaction(engine) as db:yield db
        with patch('backend.history.service.account_transaction',delayed):
            self.assertEqual(self.update(h,title='must not commit').status_code,401)
        with Session(self.engine) as db:self.assertEqual(db.get(QueryHistory,h['entry']['history_id']).version,1)

    def test_event_failure_rolls_back_save_update_and_delete(self):
        with self.engine.begin() as c:c.exec_driver_sql("CREATE TRIGGER reject_history BEFORE INSERT ON history_events BEGIN SELECT RAISE(ABORT,'explicit event failure');END")
        body=self.body();r=self.submit(body);self.assertEqual(r.status_code,503,r.text)
        self.assertEqual(r.json()['detail'],'HISTORY_SAVE_FAILED');self.assertEqual(self.count(QueryHistory),0);self.assertEqual(self.count(QueryHistoryHit),0)
        self.assertEqual(self.submit(body).status_code,409)
        with self.engine.begin() as c:c.exec_driver_sql('DROP TRIGGER reject_history')
        h=self.saved()
        with self.engine.begin() as c:c.exec_driver_sql("CREATE TRIGGER reject_history BEFORE INSERT ON history_events BEGIN SELECT RAISE(ABORT,'explicit event failure');END")
        self.assertEqual(self.update(h,title='rollback').status_code,503)
        self.assertEqual(self.remove(h).status_code,503)
        with Session(self.engine) as db:
            history=db.get(QueryHistory,h['entry']['history_id']);self.assertEqual(history.title,'fresh private question');self.assertEqual(history.version,1)
            self.assertEqual(db.get(QueryRequest,history.request_row_id).status,'completed')

    def test_quota_includes_reservations_no_eviction_and_delete_frees_slot(self):
        with patch('backend.history.service.MAX_HISTORY',2):
            a=self.saved();self.saved();calls=self.encoder.calls
            r=self.submit();self.assertEqual(r.status_code,409);self.assertEqual(r.json()['detail'],'HISTORY_LIMIT_REACHED')
            self.assertEqual(self.encoder.calls,calls);self.assertEqual(self.count(QueryHistory),2)
            self.assertEqual(self.remove(a).status_code,200);self.saved();self.assertEqual(self.count(QueryHistory),2)
        with patch('backend.history.service.MAX_HISTORY',3):
            with Session(self.engine) as db,db.begin():db.add(QueryRequest(owner_id=self.owner,request_key=str(uuid4()),input_sha256='a'*64))
            self.assertEqual(self.submit().json()['detail'],'HISTORY_LIMIT_REACHED')
            recover_history(self.engine);self.saved()

    def test_history_metadata_and_interrupted_marker_persist_across_app_restart(self):
        body=self.body();h=self.submit(body).json()['history'];r=self.update(h,title='persisted title',pinned=True);self.assertEqual(r.status_code,200)
        key=str(uuid4())
        with Session(self.engine) as db,db.begin():db.add(QueryRequest(owner_id=self.owner,request_key=key,input_sha256='a'*64))
        cookies=dict(self.client.cookies);self.client.__exit__(None,None,None)
        from tests.test_search import Encoder,VectorStore
        worker=Encoder();self.app=create_app(AuthSettings(database=self.path),model_worker=worker,qdrant=VectorStore(),ingestion_enabled=False,parsing_enabled=False,cleanup_enabled=False)
        self.engine=self.app.state.engine;self.client=TestClient(self.app);self.client.cookies.update(cookies);self.client.__enter__()
        d=self.client.get('/history/'+h['entry']['history_id']);self.assertEqual(d.status_code,200,d.text)
        self.assertEqual(d.json()['entry']['title'],'persisted title');self.assertIsNotNone(d.json()['entry']['pinned_at'])
        self.assertTrue(self.submit(body).json()['replayed']);self.assertEqual(worker.calls,0)
        with Session(self.engine) as db:self.assertEqual(db.scalar(select(QueryRequest).where(QueryRequest.request_key==key)).status,'interrupted')

    def test_no_store_safe_responses_and_nonexistent_ids(self):
        h=self.saved();url='/history/'+h['entry']['history_id']
        for r in (self.client.get('/history'),self.client.get(url),self.client.get('/history/'+str(uuid4()))):
            self.assertEqual(r.headers['cache-control'],'private, no-store');self.assertEqual(r.headers['vary'],'Cookie')
            self.assertNotIn('manifest_json',r.text);self.assertNotIn('password',r.text);self.assertNotIn('input_sha256',r.text)
