"""3-1A real migrated SQLite/cookies, transaction rollback and concurrent writers."""
from concurrent.futures import ThreadPoolExecutor
import json
import secrets
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth.accounts import AccountError, change_account, create_account
from backend.db.connection import make_engine
from backend.db.models import AccountEvent, AuthSession, User
from tests import test_auth as fixture


class AccountTests(unittest.TestCase):
    setUp = fixture.AuthTests.setUp
    tearDown = fixture.AuthTests.tearDown
    post = fixture.AuthTests.post
    login = fixture.AuthTests.login
    change_password = fixture.AuthTests.change_password
    other = fixture.AuthTests.other
    status = fixture.AuthTests.status

    def ready(self, name="admin", client=None):
        self.change_password(name, client)
        return self.login(name, client).json()["csrf_token"]

    def uid(self, name):
        with Session(self.app.state.engine) as db:
            return db.scalar(select(User.id).where(User.username == name))

    def active(self, uid, active, csrf, client=None):
        return (client or self.client).patch('/admin/users/'+uid, json={'active':active},
            headers={'Origin':fixture.ORIGIN,'X-CSRF-Token':csrf})

    def events(self):
        with Session(self.app.state.engine) as db:
            return [dict(action=e.action,source=e.source,actor_id=e.actor_id,target_id=e.target_id,
                         target_ref=e.target_ref,outcome=e.outcome,code=e.code,occurred_at=e.occurred_at)
                    for e in db.scalars(select(AccountEvent).order_by(AccountEvent.occurred_at,AccountEvent.id))]

    def test_anonymous_user_first_change_and_all_operations(self):
        uid=self.uid('A')
        def requests(csrf='x'):
            return [self.client.get('/admin/users'),
                self.post('/admin/users',{'username':'new','password':secrets.token_urlsafe(24)},csrf),
                self.active(uid,False,csrf),self.post('/admin/users/'+uid+'/password',{'password':secrets.token_urlsafe(24)},csrf),
                self.post('/admin/users/'+uid+'/sessions/revoke',{},csrf)]
        for r in requests():self.status(r,401)
        self.login('admin')
        for r in requests():self.status(r,403);self.assertEqual(r.json()['detail'],'PASSWORD_CHANGE_REQUIRED')
        csrf=self.ready('A')
        for r in requests(csrf):self.status(r,403);self.assertEqual(r.json()['detail'],'ADMIN_REQUIRED')
        self.assertEqual(self.events(),[])

    def test_list_pagination_order_and_safe_response(self):
        self.ready()
        seen=[];offset=0
        while True:
            r=self.client.get('/admin/users',params={'limit':1,'offset':offset});self.status(r,200)
            data=r.json();seen.extend(i['username'] for i in data['items'])
            self.assertNotIn('password',json.dumps(data).replace('must_change_password',''))
            self.assertNotIn('auth_version',r.text);self.assertNotIn('csrf_token',r.text)
            if data['next_offset'] is None:break
            offset=data['next_offset']
        self.assertEqual(seen,['A','admin','B'])
        for suffix in ('?owner=x','?limit=1&limit=2','?offset=-1','?limit=101'):
            self.status(self.client.get('/admin/users'+suffix),422)

    def test_create_admin_and_user_duplicate_casefold_and_first_change(self):
        csrf=self.ready();password=secrets.token_urlsafe(24)
        for role in ('user','admin'):
            name='new-'+role
            r=self.post('/admin/users',dict(username=name,password=password,role=role),csrf)
            self.status(r,201);a=r.json()['account']
            self.assertTrue(a['active'] and a['must_change_password']);self.assertEqual(a['role'],role)
            self.assertNotIn(password,r.text)
            c=self.other();r=self.post('/auth/login',dict(username=name,password=password),client=c);self.status(r,200)
            self.status(c.get('/search',params={'q':'new question'}),403)
            self.status(self.post('/admin/users',dict(username=name.upper(),password=password),csrf),409)
        events=self.events();self.assertEqual(len(events),4)
        self.assertEqual(sum(e['code']=='USERNAME_EXISTS' for e in events),2)
        self.assertTrue(all(e['source']=='http' and e['actor_id']==self.uid('admin') for e in events))

    def test_origin_csrf_strict_validation_and_no_sensitive_events(self):
        csrf=self.ready();uid=self.uid('A');password=secrets.token_urlsafe(24)
        body=dict(username='safe',password=password)
        self.status(self.client.post('/admin/users',json=body),403)
        self.status(self.post('/admin/users',body),403)
        self.status(self.post('/admin/users',body,'bad'),403)
        self.status(self.client.post('/admin/users',json=body,headers=[('Origin',fixture.ORIGIN),('X-CSRF-Token',csrf),('X-CSRF-Token',csrf)]),403)
        for update in ({'active':False},{'owner_id':uid},{'must_change_password':False},{'username':'空白'}, {'password':'short'}, {'role':'root'}):
            self.status(self.post('/admin/users',{**body,**update},csrf),422)
        self.status(self.client.patch('/admin/users/'+uid,json={'active':'false'},headers={'Origin':fixture.ORIGIN,'X-CSRF-Token':csrf}),422)
        self.status(self.post('/admin/users/'+uid+'/sessions/revoke',{'password':password},csrf),422)
        self.status(self.post('/admin/users?role=admin',body,csrf),422)
        self.assertEqual(self.events(),[])

    def test_last_enabled_admin_http_and_cli_unchanged(self):
        csrf=self.ready();uid=self.uid('admin')
        with Session(self.app.state.engine) as db:
            before=(db.get(User,uid).auth_version,db.get(User,uid).updated_at)
        r=self.active(uid,False,csrf);self.status(r,409);self.assertEqual(r.json()['detail'],'LAST_ACTIVE_ADMIN')
        with self.assertRaisesRegex(AccountError,'LAST_ACTIVE_ADMIN'):
            change_account(self.app.state.engine,'ADMIN','disable',self.timestamp)
        with Session(self.app.state.engine) as db:
            u=db.get(User,uid);self.assertTrue(u.active);self.assertEqual((u.auth_version,u.updated_at),before)
        self.status(self.client.get('/auth/me'),200)
        self.assertEqual([e['outcome'] for e in self.events()],['rejected','rejected'])

    def test_disabled_admin_does_not_count_and_self_disable_needs_other_active(self):
        csrf=self.ready();password=secrets.token_urlsafe(24)
        r=self.post('/admin/users',dict(username='second',password=password,role='admin'),csrf)
        uid=r.json()['account']['user_id']
        self.status(self.active(uid,False,csrf),200)
        self.status(self.active(self.uid('admin'),False,csrf),409)
        self.status(self.active(uid,True,csrf),200)
        self.status(self.active(self.uid('admin'),False,csrf),200)
        self.status(self.client.get('/admin/users'),401)

    def test_disable_enable_noop_and_all_old_sessions_stay_revoked(self):
        csrf=self.ready();a=self.other();self.ready('A',a);uid=self.uid('A')
        old=a.cookies.get(self.settings.cookie_name)
        self.status(self.active(uid,False,csrf),200);self.status(a.get('/auth/me'),401)
        r=self.active(uid,False,csrf);self.assertFalse(r.json()['changed'])
        self.status(self.post('/auth/login',dict(username='A',password=self.passwords['A']),client=a),401)
        self.status(self.active(uid,True,csrf),200)
        a.cookies.clear();a.cookies.set(self.settings.cookie_name,old);self.status(a.get('/auth/me'),401)
        a.cookies.clear()
        self.status(self.login('A',a),200)
        current=a.cookies.get(self.settings.cookie_name)
        r=self.active(uid,True,csrf);self.assertFalse(r.json()['changed']);self.status(a.get('/auth/me'),200)
        self.assertEqual(a.cookies.get(self.settings.cookie_name),current)
        self.assertEqual(sorted(e['outcome'] for e in self.events()),['noop','noop','success','success'])

    def test_reset_revokes_all_and_forces_new_password_change(self):
        csrf=self.ready();a=self.other();self.ready('A',a);uid=self.uid('A');b=self.other();self.login('A',b)
        new=secrets.token_urlsafe(24)
        r=self.post('/admin/users/'+uid+'/password',{'password':new},csrf);self.status(r,200)
        for c in (a,b):self.status(c.get('/auth/me'),401)
        self.status(self.post('/auth/login',dict(username='A',password=self.passwords['A']),client=a),401)
        r=self.post('/auth/login',dict(username='A',password=new),client=a);self.status(r,200);self.assertTrue(r.json()['must_change_password'])
        self.status(a.get('/documents'),403)
        self.passwords['A']=new;self.change_password('A',a);self.status(self.login('A',a),200)
        self.status(a.get('/documents'),200)
        encoded=json.dumps(self.events());self.assertNotIn(new,encoded);self.assertNotIn('password_hash',encoded)

    def test_self_revoke_and_reset_return_once_then_require_login(self):
        csrf=self.ready();uid=self.uid('admin')
        self.status(self.post('/admin/users/'+uid+'/sessions/revoke',{},csrf),200)
        self.status(self.client.get('/admin/users'),401)
        csrf=self.login('admin').json()['csrf_token'];new=secrets.token_urlsafe(24)
        self.status(self.post('/admin/users/'+uid+'/password',{'password':new},csrf),200)
        self.status(self.client.get('/auth/me'),401)
        self.passwords['admin']=new;self.assertTrue(self.login('admin').json()['must_change_password'])

    def test_missing_target_is_audited_and_role_change_is_not_supported(self):
        csrf=self.ready();uid=str(uuid4())
        self.status(self.active(uid,False,csrf),404)
        self.status(self.post('/admin/users/'+uid+'/sessions/revoke',{},csrf),404)
        self.status(self.client.patch('/admin/users/'+self.uid('A'),json={'role':'admin'},headers={'Origin':fixture.ORIGIN,'X-CSRF-Token':csrf}),422)
        self.assertTrue(all(e['outcome']=='rejected' and e['code']=='ACCOUNT_NOT_FOUND' for e in self.events()))

    def test_event_failure_rolls_back_account_and_session_changes(self):
        csrf=self.ready();a=self.other();self.ready('A',a);uid=self.uid('A')
        with self.app.state.engine.begin() as db:
            db.exec_driver_sql("CREATE TRIGGER reject_events BEFORE INSERT ON account_events BEGIN SELECT RAISE(ABORT, 'explicit event failure'); END")
        with Session(self.app.state.engine) as db:u=db.get(User,uid);version=u.auth_version
        self.status(self.active(uid,False,csrf),503)
        with Session(self.app.state.engine) as db:u=db.get(User,uid);self.assertTrue(u.active);self.assertEqual(u.auth_version,version)
        self.status(a.get('/auth/me'),200);self.assertEqual(self.events(),[])
        self.status(self.post('/admin/users',dict(username='rollback',password=secrets.token_urlsafe(24)),csrf),503)
        self.assertIsNone(self.uid('rollback'))

    def test_cli_two_connections_concurrent_disable_never_zero(self):
        create_account(self.app.state.engine,'second',secrets.token_urlsafe(24),'admin',self.timestamp)
        other_engine=make_engine(self.path);barrier=threading.Barrier(2)
        def run(engine,name):
            barrier.wait(timeout=5)
            try:change_account(engine,name,'disable',self.timestamp);return 'disabled'
            except AccountError as e:return e.code
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                a=pool.submit(run,self.app.state.engine,'admin');b=pool.submit(run,other_engine,'second')
                outcomes=[a.result(10),b.result(10)]
            self.assertCountEqual(outcomes,['disabled','LAST_ACTIVE_ADMIN'])
            with Session(self.app.state.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(User).where(User.role=='admin',User.active.is_(True))),1)
        finally:other_engine.dispose()

    def test_http_two_admins_concurrent_self_disable_never_zero(self):
        csrf1=self.ready();password=secrets.token_urlsafe(24)
        self.post('/admin/users',dict(username='second',password=password,role='admin'),csrf1)
        self.passwords['second']=password;c2=self.other();csrf2=self.ready('second',c2)
        barrier=threading.Barrier(2)
        def run(client,name,csrf):
            barrier.wait(timeout=5)
            return self.active(self.uid(name),False,csrf,client).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(run,self.client,'admin',csrf1);b=pool.submit(run,c2,'second',csrf2)
            self.assertCountEqual([a.result(10),b.result(10)],[200,409])
        with Session(self.app.state.engine) as db:self.assertEqual(db.scalar(select(func.count()).select_from(User).where(User.role=='admin',User.active.is_(True))),1)

    def test_http_cross_disable_rechecks_actor_inside_lock(self):
        csrf1=self.ready();password=secrets.token_urlsafe(24)
        self.post('/admin/users',dict(username='second',password=password,role='admin'),csrf1)
        self.passwords['second']=password;c2=self.other();csrf2=self.ready('second',c2)
        barrier=threading.Barrier(2)
        def run(client,target,csrf):
            barrier.wait(timeout=5)
            return self.active(self.uid(target),False,csrf,client).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(run,self.client,'second',csrf1);b=pool.submit(run,c2,'admin',csrf2)
            self.assertCountEqual([a.result(10),b.result(10)],[200,401])

    def test_revoked_after_cookie_load_cannot_mutate(self):
        csrf=self.ready();entered=threading.Event();release=threading.Event()
        original=change_account
        def pause(*args,**kwargs):
            entered.set();self.assertTrue(release.wait(5));return original(*args,**kwargs)
        with patch('backend.auth.admin.change_account',pause),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.active,self.uid('A'),False,csrf)
            self.assertTrue(entered.wait(5))
            original(self.app.state.engine,'admin','revoke',self.timestamp)
            release.set();self.status(future.result(10),401)
        with Session(self.app.state.engine) as db:self.assertTrue(db.get(User,self.uid('A')).active)

    def test_concurrent_duplicate_create_one_account_and_two_events(self):
        barrier=threading.Barrier(2);password=secrets.token_urlsafe(24)
        def run(name):
            barrier.wait(timeout=5)
            try:create_account(self.app.state.engine,name,password,'user',self.timestamp);return 'created'
            except AccountError as e:return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(run,'NewName');b=pool.submit(run,'newname')
            self.assertCountEqual([a.result(10),b.result(10)],['created','USERNAME_EXISTS'])
        self.assertEqual(len(self.events()),2)

    def test_lock_timeout_fails_closed_and_leaves_no_event(self):
        csrf=self.ready();uid=self.uid('A')
        # Separate connection with short busy timeout; the writer owns BEGIN IMMEDIATE.
        with self.app.state.engine.connect() as lock:
            lock.exec_driver_sql('BEGIN IMMEDIATE')
            with self.app.state.engine.connect() as c:c.exec_driver_sql('PRAGMA busy_timeout=20');c.commit()
            try:
                self.status(self.active(uid,False,csrf),503)
            finally:lock.rollback()
        self.assertEqual(self.events(),[])
        with Session(self.app.state.engine) as db:self.assertTrue(db.get(User,uid).active)
