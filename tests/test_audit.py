"""Migrated SQLite and real auth/transactions; explicit inference doubles never used by audit."""
import json,time
from unittest.mock import patch
from uuid import uuid4
import unittest
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from backend.auth.accounts import change_account
from backend.db.models import (User,Document,DocumentVersion,AccountEvent,SharingEvent,DeletionEvent,HistoryEvent,
    Job,ParsingTask,ParserProfile,DocumentCleanup,QueryRequest)
from backend.audit import service
from tests import test_search as fixture

class AuditTests(unittest.TestCase):
    login=fixture.SearchTests.login
    tearDown=fixture.SearchTests.tearDown
    def setUp(self):
        fixture.SearchTests.setUp(self);self.login('admin');self.t=int(time.time());self.params={'since':self.t-100,'until':self.t+100}
        with Session(self.engine) as db,db.begin():
            self.users={u.username:u.id for u in db.scalars(select(User))};self.doc=db.scalar(select(Document).where(Document.owner_id==self.users['A'])).id
            self.version=db.scalar(select(DocumentVersion.id).where(DocumentVersion.document_id==self.doc))
            db.add_all([
                AccountEvent(id=str(uuid4()),actor_id=self.users['admin'],target_id=self.users['A'],target_ref='SECRET_USERNAME',source='http',action='revoke',outcome='success',code='OK',occurred_at=self.t),
                AccountEvent(actor_id=None,target_ref='PRIVATE_REF',source='cli',action='enable',outcome='rejected',code='ACCOUNT_NOT_FOUND',occurred_at=self.t-1),
                SharingEvent(actor_id=self.users['admin'],document_id=self.doc,action='unpublish',outcome='noop',code='OK',before_version=1,after_version=1,occurred_at=self.t),
                DeletionEvent(actor_id=None,document_id=self.doc,action='cleanup',outcome='failed',code='CLEANUP_STORAGE_FAILED',attempt=1,occurred_at=self.t),
                HistoryEvent(actor_id=self.users['A'],history_id=str(uuid4()),action='delete',outcome='success',version=2,occurred_at=self.t)])
            self.job=str(uuid4());db.add(Job(id=self.job,owner_id=self.users['A'],document_version_id=self.version,upload_key=str(uuid4()),request_sha256='a'*64,upload_bytes=12,status='failed',stage='encoding',progress=20,attempt=2,error_code='PAGE_ENCODING_FAILED'))
            profile=ParserProfile(config_json='SECRET_CONFIG',config_sha256='b'*64);db.add(profile);db.flush()
            db.add(ParsingTask(document_version_id=self.version,parser_profile_id=profile.id,status='partial',attempt=1,error_code='PARSER_PAGE_ERRORS'))
            db.add(DocumentCleanup(document_id=self.doc,status='failed',attempt=3,stage='files',error_code='CLEANUP_STORAGE_FAILED',manifest_json='SECRET_MANIFEST'))
            self.marker=str(uuid4());db.add(QueryRequest(id=self.marker,owner_id=self.users['B'],request_key=str(uuid4()),input_sha256='c'*64,status='failed',error_code='HISTORY_EXECUTION_FAILED'))
    def get(self,path='/admin/events',**params):return self.client.get(path,params={**self.params,**params})
    def change(self,model,key,**values):
        with Session(self.engine) as db,db.begin():
            row=db.get(model,key)
            for k,v in values.items():setattr(row,k,v)
    def test_auth_role_first_change_and_no_store(self):
        for path in ('/admin/events','/admin/tasks'):
            self.client.cookies.clear();r=self.get(path);self.assertEqual(r.status_code,401);self.assertEqual(r.headers['cache-control'],'private, no-store')
            self.login('A');self.assertEqual(self.get(path).status_code,403)
            self.login('admin');self.change(User,self.users['admin'],must_change_password=True);self.assertEqual(self.get(path).json()['detail'],'PASSWORD_CHANGE_REQUIRED');self.change(User,self.users['admin'],must_change_password=False)
        self.assertEqual(self.encoder.calls,0)
    def test_strict_duplicate_extra_UUID_enum_and_time_window(self):
        for query in ('limit=1&limit=2','secret=x','since=1&until=1','since=0&until=9999999','since=-1','since=1.0','limit=1.0','actor_id=no','category=all','outcome=bad'):
            self.assertEqual(self.client.get('/admin/events?'+query).status_code,422,query)
        for query in ('kind=all','status=no','owner_id=no','document_id=no','q=PRIVATE','offset=-1'):
            self.assertEqual(self.client.get('/admin/tasks?'+query).status_code,422,query)
    def test_four_event_sources_fields_and_no_private_names(self):
        r=self.get();self.assertEqual(r.status_code,200,r.text);items=r.json()['items'];self.assertEqual({i['category'] for i in items},{'account','sharing','deletion','history'})
        self.assertEqual({i['actor_type'] for i in items},{'user','cli','system'})
        for secret in ('SECRET_USERNAME','PRIVATE_REF','SECRET_CONFIG','SECRET_MANIFEST','target_ref','password','csrf','preview','display_name'):self.assertNotIn(secret,r.text)
        self.assertEqual(set(items[0]),{'event_id','category','actor_id','target_id','actor_type','action','outcome','code','occurred_at'})
    def test_events_filters_window_and_stable_tied_pagination(self):
        all_items=self.get().json()['items'];a=self.get(limit=2).json();b=self.get(limit=2,offset=2).json();c=self.get(limit=2,offset=4).json()
        self.assertEqual(a['items']+b['items']+c['items'],all_items);self.assertIsNone(c['next_offset']);self.assertEqual(a['scope_version'],b['scope_version'])
        self.assertEqual(len(self.get(category='history',actor_id=self.users['A'],outcome='success').json()['items']),1)
        self.assertEqual(len(self.get(target_id=self.doc).json()['items']),2)
        self.assertEqual(self.get(since=self.t-1,until=self.t).json()['items'][0]['actor_type'],'cli')
        self.assertEqual(self.get(since=self.t+1,until=self.t+2).json()['items'],[])
    def test_four_task_kinds_filters_status_and_no_executor(self):
        r=self.get('/admin/tasks');self.assertEqual(r.status_code,200,r.text);self.assertEqual({i['kind'] for i in r.json()['items']},{'ingest','parsing','cleanup','search'})
        for kind in ('ingest','parsing','cleanup','search'):self.assertEqual(len(self.get('/admin/tasks',kind=kind).json()['items']),1)
        self.assertEqual(len(self.get('/admin/tasks',status='failed').json()['items']),3)
        self.assertEqual(len(self.get('/admin/tasks',document_id=self.doc,owner_id=self.users['A']).json()['items']),3)
        search=self.get('/admin/tasks',kind='search').json()['items'][0];self.assertIsNone(search['document_id']);self.assertNotIn('request_key',r.text);self.assertNotIn('input_sha256',r.text);self.assertNotIn('manifest_json',r.text);self.assertEqual(self.encoder.calls,0)
    def test_error_stage_and_created_timestamp_cannot_export_free_text(self):
        self.change(Job,self.job,error_code='PASSWORD_OR_PATH_SECRET',stage='C:/SECRET',created_at='https://SECRET')
        with Session(self.engine) as db,db.begin():row=db.scalar(select(AccountEvent));row.code='COOKIE_SECRET'
        r=self.get('/admin/tasks',kind='ingest');item=r.json()['items'][0];self.assertEqual(item['error_code'],'OTHER');self.assertEqual(item['stage'],'other');self.assertIsNone(item['created_at']);self.assertNotIn('SECRET',r.text)
        self.assertNotIn('COOKIE_SECRET',self.get().text)
    def test_revoked_after_first_snapshot_rejected(self):
        original=service.snapshot;calls=[]
        def snapshot(*args):
            value=original(*args);calls.append(1)
            if len(calls)==1:change_account(self.engine,'admin','revoke',time.time())
            return value
        with patch.object(service,'snapshot',snapshot):self.assertEqual(self.get().status_code,401)
        self.assertEqual(len(calls),1)
    def test_role_changed_after_first_snapshot_rejected(self):
        original=service.snapshot
        def snapshot(*args):
            value=original(*args);self.change(User,self.users['admin'],role='user');return value
        with patch.object(service,'snapshot',snapshot):self.assertEqual(self.get('/admin/tasks').status_code,403)
    def test_task_changed_during_read409_and_no_stale_success(self):
        original=service.snapshot;calls=[]
        def snapshot(*args):
            value=original(*args);calls.append(1)
            if len(calls)==1:self.change(Job,self.job,progress=21)
            return value
        with patch.object(service,'snapshot',snapshot):self.assertEqual(self.get('/admin/tasks').status_code,409)
    def test_read_only_and_no_management_or_private_read_bypass(self):
        def rows():
            with Session(self.engine) as db:return {n:db.execute(text('select * from '+n)).all() for n in ('account_events','sharing_events','deletion_events','history_events','jobs','query_requests','query_histories')}
        before=rows();self.get();self.get('/admin/tasks');self.assertEqual(before,rows())
        self.assertEqual(self.client.get('/documents/'+self.doc).status_code,404)
        self.assertEqual(self.client.post('/admin/tasks',json={},headers={'Origin':'http://127.0.0.1:3000'}).status_code,405)
    def test_deleted_history_keeps_only_metadata_and_owner410(self):
        self.login('A');headers={'Origin':'http://127.0.0.1:3000','X-CSRF-Token':self.client.get('/auth/me').json()['csrf_token']}
        body={'q':'PRIVATE_QUERY_NEVER_ADMIN','request_id':str(uuid4()),'k':3};r=self.client.post('/search',json=body,headers=headers);self.assertEqual(r.status_code,200,r.text)
        entry=r.json()['history']['entry'];url='/history/'+entry['history_id'];self.assertEqual(self.client.request('DELETE',url,json={'version':entry['version'],'confirmed':True},headers=headers).status_code,200)
        self.assertEqual(self.client.post('/search',json=body,headers=headers).status_code,410)
        self.login('admin');self.assertEqual(self.client.get(url).status_code,404)
        r=self.get(category='history',target_id=entry['history_id']);self.assertEqual({i['action'] for i in r.json()['items']},{'create','delete'});self.assertNotIn(body['q'],r.text+self.get('/admin/tasks').text)
    def test_missing_source_database_failure503_no_private_exception(self):
        with self.engine.begin() as c:c.exec_driver_sql('DROP TABLE history_events')
        r=self.get();self.assertEqual(r.status_code,503);self.assertEqual(r.json(),{'detail':'SERVICE_UNAVAILABLE'})
