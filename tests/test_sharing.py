"""Real migrated SQLite/cookies/PNG; explicit inference doubles for race contracts."""
from concurrent.futures import ThreadPoolExecutor
import json
import threading
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.auth.accounts import change_account
from backend.db.models import Document, SharingEvent, User
from backend.documents.routes import read_verified_image
from backend.documents.sharing import change_sharing
from tests import test_region_routes as fixture

class SharingTests(unittest.TestCase):
    login=fixture.RegionRoutes.login
    tearDown=fixture.RegionRoutes.tearDown
    change=fixture.RegionRoutes.change

    def setUp(self):
        fixture.RegionRoutes.setUp(self)
        self.admin=TestClient(self.app);self.addCleanup(self.admin.close)
        response=self.admin.post('/auth/login',json={'username':'admin','password':self.passwords['admin']},headers={'Origin':fixture.ORIGIN})
        self.admin_headers={'Origin':fixture.ORIGIN,'X-CSRF-Token':response.json()['csrf_token']}
        with Session(self.engine) as db,db.begin():
            self.admin_id=db.scalar(select(User.id).where(User.username=='admin'))
            db.get(Document,self.doc).owner_id=self.admin_id

    def body(self):
        with Session(self.engine) as db:
            d=db.get(Document,self.doc)
            return {'document_version_id':d.active_version_id,'access_version':d.access_version,'confirmed':True}

    def write(self,action='publish',body=None,client=None,headers=None,doc=None):
        return (client or self.admin).post('/admin/documents/'+(doc or self.doc)+'/'+action,
            json=body if body is not None else self.body(),headers=self.admin_headers if headers is None else headers)

    def event_rows(self):
        with Session(self.engine) as db:return [(e.action,e.outcome,e.code,e.before_version,e.after_version) for e in db.scalars(select(SharingEvent))]

    def test_permissions_first_change_origin_csrf_and_own_scope(self):
        self.assertEqual(self.client.get('/admin/documents').status_code,403)
        for action in ('publish','unpublish'):self.assertEqual(self.write(action,client=self.client,headers=self.headers).status_code,403)
        self.admin.cookies.clear();self.assertEqual(self.admin.get('/admin/documents').status_code,401)
        self.assertEqual(self.write().status_code,401)
        self.admin.post('/auth/login',json={'username':'admin','password':self.passwords['admin']},headers={'Origin':fixture.ORIGIN})
        self.assertEqual(self.write(headers={}).status_code,403)
        self.assertEqual(self.write(headers={'Origin':fixture.ORIGIN,'X-CSRF-Token':'wrong'}).status_code,403)
        self.change(User,self.admin_id,must_change_password=True)
        self.assertEqual(self.admin.get('/admin/documents').status_code,403)
        self.assertEqual(self.event_rows(),[])

    def test_management_list_never_includes_other_users_or_admins_private(self):
        response=self.admin.get('/admin/documents');self.assertEqual(response.status_code,200)
        self.assertEqual([i['document_id'] for i in response.json()['items']],[self.doc])
        with Session(self.engine) as db:other=db.scalar(select(Document).where(Document.owner_id!=self.admin_id)).id
        self.assertEqual(self.write(doc=other).status_code,404)
        # Role alone grants no cross-owner private management.
        self.change(User,self.owner,role='admin')
        self.assertEqual(self.write(client=self.client,headers=self.headers).status_code,404)
        self.assertEqual(self.event_rows(),[])

    def test_strict_parameters_confirmation_and_event_fields(self):
        for update in ({'confirmed':False},{'confirmed':'true'},{'access_version':True},{'access_version':0},{'owner_id':self.owner},{'visibility':'shared'}):
            self.assertEqual(self.write(body={**self.body(),**update}).status_code,422)
        for query in ('?owner=x','?limit=1&limit=2','?offset=-1'):
            self.assertEqual(self.admin.get('/admin/documents'+query).status_code,422)
        self.assertEqual(self.admin.post('/admin/documents/'+self.doc+'/publish?x=1',json=self.body(),headers=self.admin_headers).status_code,422)
        self.assertEqual(self.event_rows(),[])
        self.assertEqual(self.write().status_code,200)
        self.assertNotIn('password',json.dumps(self.event_rows()))

    def test_publish_unpublish_both_users_and_old_links_never_revive(self):
        self.assertEqual(self.client.get('/search',params={'q':'before','document_id':self.doc}).status_code,404)
        self.assertTrue(self.write().json()['changed'])
        old_preview=None;old_crop=None
        for name in ('A','B'):
            self.login(name);self.headers['X-CSRF-Token']=self.client.get('/auth/me').json()['csrf_token']
            self.assertIn(self.doc,[i['document_id'] for i in self.client.get('/documents').json()['items']])
            hit=self.client.get('/search',params={'q':'fresh '+name,'document_id':self.doc}).json()['items'][0]
            self.assertEqual(self.client.get(hit['preview_url']).status_code,200)
            ranked=self.client.post(self.url,json=self.action,headers=self.headers)
            self.assertEqual(ranked.status_code,200);crop=ranked.json()['items'][0]['crop_url']
            self.assertEqual(self.client.get(crop).status_code,200)
            self.assertFalse(ranked.json()['can_parse'])
            self.assertEqual(self.client.post('/documents/'+self.doc+'/parsing',json={},headers=self.headers).status_code,404)
            old_preview=hit['preview_url'];old_crop=crop
        self.assertEqual(self.write('unpublish').status_code,200)
        for url in (old_preview,old_crop,self.url+'/status'):
            self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.post(self.url,json=self.action,headers=self.headers).status_code,404)
        self.assertEqual(self.client.get('/search',params={'q':'withdrawn','document_id':self.doc}).status_code,404)
        self.assertEqual(self.write().status_code,200)
        self.assertEqual(self.client.get(old_preview).status_code,404)
        self.assertEqual(self.client.get(old_crop).status_code,404)
        fresh=self.client.get('/search',params={'q':'republished','document_id':self.doc}).json()['items'][0]
        self.assertEqual(self.client.get(fresh['preview_url']).status_code,200)

    def test_noop_keeps_epoch_stale_input_conflicts_and_audits(self):
        initial=self.body();r=self.write('unpublish');self.assertFalse(r.json()['changed'])
        self.assertEqual(r.json()['document']['access_version'],1)
        self.write();self.assertEqual(self.write(body=initial).status_code,409)
        self.assertFalse(self.write().json()['changed'])
        self.assertEqual([e[1] for e in self.event_rows()],['noop','success','rejected','noop'])
        self.assertEqual(self.body()['access_version'],2)

    def test_unready_publish_refused_but_unpublish_not_blocked_by_index(self):
        self.change(Document,self.doc,status='registered')
        self.assertEqual(self.write().status_code,409)
        self.change(Document,self.doc,status='ready');self.write()
        self.change(Document,self.doc,status='registered')
        self.assertEqual(self.write('unpublish').status_code,200)

    def test_event_failure_rolls_back_visibility_and_epoch(self):
        with self.engine.begin() as c:c.exec_driver_sql("CREATE TRIGGER fail_share BEFORE INSERT ON sharing_events BEGIN SELECT RAISE(ABORT,'explicit test failure'); END")
        self.assertEqual(self.write().status_code,503)
        self.assertEqual(self.body()['access_version'],1)
        with Session(self.engine) as db:self.assertEqual(db.get(Document,self.doc).visibility,'private')
        self.assertEqual(self.event_rows(),[])

    def test_concurrent_same_version_one_success_one_conflict(self):
        other=TestClient(self.app);self.addCleanup(other.close)
        me=other.post('/auth/login',json={'username':'admin','password':self.passwords['admin']},headers={'Origin':fixture.ORIGIN}).json()
        headers={'Origin':fixture.ORIGIN,'X-CSRF-Token':me['csrf_token']};body=self.body();barrier=threading.Barrier(2)
        def run(client,headers):barrier.wait(5);return self.write(body=body,client=client,headers=headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(run,self.admin,self.admin_headers);b=pool.submit(run,other,headers)
            self.assertCountEqual([a.result(10),b.result(10)],[200,409])
        self.assertEqual(self.body()['access_version'],2)

    def test_revocation_after_cookie_load_rechecked_under_write_lock(self):
        entered=threading.Event();release=threading.Event()
        def pause(*args,**kwargs):entered.set();self.assertTrue(release.wait(5));return change_sharing(*args,**kwargs)
        with patch('backend.documents.sharing.change_sharing',pause),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.write);self.assertTrue(entered.wait(5))
            change_account(self.engine,'admin','revoke',1794110400);release.set()
            self.assertEqual(future.result(10).status_code,401)
        self.assertEqual(self.event_rows(),[])

    def cycle(self):self.write('unpublish');self.write()

    def test_search_ABA_during_query_returns_conflict(self):
        self.write();self.encoder.callback=self.cycle
        r=self.client.get('/search',params={'q':'race','document_id':self.doc})
        self.assertEqual(r.status_code,409)

    def test_PNG_ABA_during_read_refused(self):
        self.write();hit=self.client.get('/search',params={'q':'image race','document_id':self.doc}).json()['items'][0]
        def read(page):data=read_verified_image(page);self.cycle();return data
        with patch('backend.documents.routes.read_verified_image',read):self.assertEqual(self.client.get(hit['preview_url']).status_code,404)

    def test_region_and_crop_ABA_during_processing_refused(self):
        self.write();self.region_worker.callback=self.cycle
        self.assertEqual(self.client.post(self.url,json=self.action,headers=self.headers).status_code,409)
        self.region_worker.callback=None
        crop=self.client.post(self.url,json=self.action,headers=self.headers).json()['items'][0]['crop_url']
        def read(page):data=read_verified_image(page);self.cycle();return data
        with patch('backend.regions.routes.read_verified_image',read):self.assertEqual(self.client.get(crop).status_code,404)
