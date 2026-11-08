"""R24 / 3-1A isolated migration, real localhost admin HTTP, original CPU retrieval/regions.

Formal DB and retained R22 source are read-only. Random credentials remain in
ignored runtime. No PDF upload, page encoding, parser run or production restart.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import time

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.settings import AuthSettings
from backend.db.connection import ROOT, make_engine
from backend.db.models import AccountEvent, AuthSession, Document, LoginAttempt, Page, PageFeature, User
from backend.db.seed import password_hasher
from backend.main import create_app
from backend.search.worker import ModelWorker
from backend.search.settings import SearchSettings
from scripts.migrate_database import migrate
from runtime.verification.r24.preflight import snapshot

OUT=ROOT/'runtime/verification/r24'
ORIGIN='http://127.0.0.1:3000'
DB=OUT/'metadata.sqlite3'
REGION_DB=OUT/'regions.sqlite3'


def save(path,data):
    with path.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)


def clone(source,dest):
    assert source.exists() and not dest.exists()
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(dest)) as dst:
        src.execute('PRAGMA query_only=ON');src.backup(dst)


def prepare():
    clone(ROOT/'runtime/metadata.sqlite3',DB)
    before=snapshot(DB);migrate(DB);after=snapshot(DB);migrate(DB);repeat=snapshot(DB)
    assert before['revision']=='0008_parsing' and after['revision']=='0009_account_events'
    assert set(after['tables'])-set(before['tables'])=={'account_events'}
    assert all(after['tables'][k]==v for k,v in before['tables'].items() if k!='alembic_version')
    assert after==repeat and after['tables']['account_events']['count']==0
    save(OUT/'migration.json',{'round':'R24','overall':'passed','before':before,'after':after,'repeat_identical':True,
         'scope':'Nonempty formal clone only; all prior tables identical, only account_events and revision added; no formal migration.'})
    clone(ROOT/'runtime/verification/r22/metadata.sqlite3',REGION_DB);migrate(REGION_DB)
    passwords={name:secrets.token_urlsafe(24) for name in ('A','B','admin')}
    for path in (DB,REGION_DB):
        engine=make_engine(path)
        try:
            with Session(engine) as db,db.begin():
                db.query(AuthSession).delete();db.query(LoginAttempt).delete()
                for u in db.scalars(select(User)):
                    u.password_hash=password_hasher.hash(passwords[u.username]);u.must_change_password=False;u.auth_version+=1;u.active=True
        finally:engine.dispose()
    save(OUT/'private.json',{'passwords':passwords})
    print('R24 isolated clones ready; additive/repeat migration verified; random credentials not printed')


def state():return json.loads((OUT/'private.json').read_text('utf-8'))


def cli():
    checks,check,_=harness()
    commands=[('disable','admin',1,'LAST_ACTIVE_ADMIN'),('enable','admin',0,'sessions unchanged')]
    for action,name,exitcode,expected in commands:
        result=subprocess.run([sys.executable,'-B','-m','scripts.manage_account',action,name,'--database',str(DB)],
                              cwd=ROOT,capture_output=True,text=True)
        check('cli_'+action+'_exit_and_result',result.returncode==exitcode and expected in result.stdout+result.stderr)
    engine=make_engine(DB)
    try:
        with Session(engine) as db:
            events=list(db.scalars(select(AccountEvent).where(AccountEvent.source=='cli')))
            check('CLI_shared_guard_and_noop_events',len(events)==2 and {e.code for e in events}=={'LAST_ACTIVE_ADMIN','OK'} and all(e.actor_id is None for e in events))
            check('last_admin_stays_active',db.scalar(select(User).where(User.username=='admin')).active)
    finally:engine.dispose()
    save(OUT/'cli.json',{'round':'R24','overall':'passed','checks':checks,'scope':'Actual noninteractive CLI on isolated R24 database; no password input/output.'})
    print('R24 CLI passed:',len(checks),'checks')


def harness():
    checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        assert value,name
    def login(client,name,password):
        r=client.post('/auth/login',json={'username':name,'password':password},headers={'Origin':ORIGIN})
        check(name+'_login',r.status_code==200)
        return r.json()['csrf_token']
    return checks,check,login


def http():
    # Port 8001 was verified empty; refuse to replace an existing listener.
    import socket
    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8001))!=0
    checks,check,login=harness();passwords=state()['passwords'];log=(OUT/'http-server.log').open('x',encoding='utf-8')
    cmd=[sys.executable,'-B','-m','uvicorn','runtime.verification.r24.acceptance_server:app','--host','127.0.0.1','--port','8001','--workers','1','--no-access-log']
    proc=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    clients=[httpx.Client(base_url='http://127.0.0.1:8001',timeout=20,trust_env=False) for _ in range(3)]
    admin,a,b=clients
    try:
        deadline=time.monotonic()+25
        while True:
            try:
                if admin.get('/health').status_code==200:break
            except httpx.TransportError:pass
            assert proc.poll() is None and time.monotonic()<deadline,'isolation server not ready'
            time.sleep(.15)
        check('anonymous_admin_401',admin.get('/admin/users').status_code==401)
        csrf=login(admin,'admin',passwords['admin']);a_csrf=login(a,'A',passwords['A']);login(b,'B',passwords['B'])
        check('ordinary_user_list_403',a.get('/admin/users').status_code==403)
        check('ordinary_user_create_403',a.post('/admin/users',json={'username':'forbidden','password':secrets.token_urlsafe(24)},headers={'Origin':ORIGIN,'X-CSRF-Token':a_csrf}).status_code==403)
        listing=admin.get('/admin/users');check('admin_list_200',listing.status_code==200)
        users={u['username']:u for u in listing.json()['items']};headers={'Origin':ORIGIN,'X-CSRF-Token':csrf}
        check('safe_account_fields',all(set(u)=={'user_id','username','role','active','must_change_password','created_at','updated_at'} for u in users.values()))
        target='/admin/users/'+users['A']['user_id'];new=secrets.token_urlsafe(24)
        check('missing_origin_403',admin.patch(target,json={'active':False}).status_code==403)
        check('wrong_csrf_403',admin.patch(target,json={'active':False},headers={'Origin':ORIGIN,'X-CSRF-Token':'wrong'}).status_code==403)
        check('last_admin_409',admin.patch('/admin/users/'+users['admin']['user_id'],json={'active':False},headers=headers).status_code==409)
        check('disable_200',admin.patch(target,json={'active':False},headers=headers).status_code==200)
        check('disabled_session_401',a.get('/auth/me').status_code==401)
        check('disabled_login_401',a.post('/auth/login',json={'username':'A','password':passwords['A']},headers={'Origin':ORIGIN}).status_code==401)
        check('repeat_disable_noop',admin.patch(target,json={'active':False},headers=headers).json()['changed'] is False)
        check('enable_200',admin.patch(target,json={'active':True},headers=headers).status_code==200)
        check('enable_does_not_revive_old_session',a.get('/auth/me').status_code==401)
        login(a,'A',passwords['A'])
        check('reset_200',admin.post(target+'/password',json={'password':new},headers=headers).status_code==200)
        check('reset_old_session_401',a.get('/auth/me').status_code==401)
        csrf_new=login(a,'A',new)
        check('reset_first_change_gate',a.get('/search',params={'q':'new question R24'}).status_code==403)
        changed=secrets.token_urlsafe(24)
        check('first_change_204',a.post('/auth/password',json={'current_password':new,'new_password':changed},headers={'Origin':ORIGIN,'X-CSRF-Token':csrf_new}).status_code==204)
        login(a,'A',changed)
        check('revoke_200',admin.post(target+'/sessions/revoke',json={},headers=headers).status_code==200)
        check('revoked_401',a.get('/auth/me').status_code==401)
        check('other_account_session_unchanged',b.get('/auth/me').status_code==200)
        created=admin.post('/admin/users',json={'username':'R24-new','password':new,'role':'user'},headers=headers)
        check('create_201_first_change',created.status_code==201 and created.json()['account']['must_change_password'])
        check('duplicate_case_409',admin.post('/admin/users',json={'username':'r24-NEW','password':new},headers=headers).status_code==409)
        check('unknown_target_404',admin.post('/admin/users/00000000-0000-4000-8000-000000000000/sessions/revoke',json={},headers=headers).status_code==404)
        check('no_store_on_success_and_rejection',listing.headers['cache-control']=='private, no-store' and created.headers['cache-control']=='private, no-store')
        engine=make_engine(DB)
        with Session(engine) as db:
            events=[{'action':e.action,'outcome':e.outcome,'code':e.code,'actor_id':e.actor_id,'target_id':e.target_id,'source':e.source,'occurred_at':e.occurred_at} for e in db.scalars(select(AccountEvent))]
        engine.dispose()
        check('atomic_minimal_events',len(events)==9 and all(e['source']=='http' and e['actor_id']==users['admin']['user_id'] for e in events))
        check('no_password_or_token_in_public_events',all(v not in json.dumps(events) for v in (new,changed,csrf)))
        save(OUT/'http.json',{'round':'R24','overall':'passed','checks':checks,'events':events,'transport':'actual localhost HTTP on isolated 8001','server_command':cmd})
        print('R24 HTTP passed:',len(checks),'checks')
    finally:
        for client in clients:client.close()
        if proc.poll() is None:
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        proc.wait(timeout=15);log.close()


def real():
    checks,check,login=harness();passwords=state()['passwords'];engine=make_engine(REGION_DB)
    worker=ModelWorker(SearchSettings(worker_timeout=420))
    worker.log=(OUT/'cpu-model.log').open('x',encoding='utf-8')
    worker.process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-B','-u','-m','runtime.verification.r24.cpu_worker'],cwd=ROOT,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=worker.log,text=True,encoding='utf-8',env={**os.environ,'PYTHONUTF8':'1'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    os.environ['LAYOUTPATCH_QUERY_AUDIT_DIR']=str(OUT/'queries')
    os.environ['LAYOUTPATCH_REGION_AUDIT_DIR']=str(OUT/'regions')
    app=create_app(AuthSettings(database=REGION_DB),model_worker=worker,ingestion_enabled=False,parsing_enabled=False)
    cases=[]
    try:
        with TestClient(app) as client,TestClient(app) as admin:
            csrf_admin=login(admin,'admin',passwords['admin']);headers_admin={'Origin':ORIGIN,'X-CSRF-Token':csrf_admin}
            for name in ('A','B'):
                client.cookies.clear();csrf=login(client,name,passwords[name]);headers={'Origin':ORIGIN,'X-CSRF-Token':csrf}
                with Session(engine) as db:
                    uid=db.scalar(select(User.id).where(User.username==name))
                    docs=list(db.scalars(select(Document).where(Document.owner_id==uid,Document.status=='ready')))
                    old=next(d.id for d in docs if not db.scalar(select(PageFeature.page_id).join(Page,Page.id==PageFeature.page_id).where(Page.document_version_id==d.active_version_id).limit(1)))
                    page=db.scalar(select(Page).join(PageFeature,PageFeature.page_id==Page.id).join(Document,Document.active_version_id==Page.document_version_id).where(Document.owner_id==uid))
                    page_id=page.id;allowed=set(db.scalars(select(Page.id).join(Document,Document.active_version_id==Page.document_version_id).where(Document.owner_id==uid,Document.status=='ready')))
                for mode in ('library','document'):
                    q=f'What does the main figure explain? R24 original CPU regression {name} {mode}.'
                    r=client.get('/search',params={'q':q,'k':3,**({'document_id':old} if mode=='document' else {})})
                    check(name+'_'+mode+'_fresh_original_search',r.status_code==200)
                    data=r.json();check(name+'_'+mode+'_scope',data['search_mode']==mode and len(data['items'])==3 and all(i['page_id'] in allowed and (mode=='library' or i['document_id']==old) for i in data['items']))
                    hit=data['items'][0];image=client.get(hit['preview_url'])
                    check(name+'_'+mode+'_PNG_hash',image.status_code==200 and hashlib.sha256(image.content).hexdigest()==hit['render_sha256'])
                    if mode=='document':
                        check(name+'_legacy_regions_unavailable',client.get('/pages/'+hit['page_id']+'/regions/status').json()['status']=='unavailable')
                    cases.append({'owner':name,'mode':mode,'items':len(data['items']),'authorized_pages':len(allowed),'query_sha256':hashlib.sha256(q.encode()).hexdigest()})
                url='/pages/'+page_id+'/regions';s=client.get(url+'/status');check(name+'_real_candidates_ready',s.status_code==200 and s.json()['status']=='ready')
                body={k:s.json()[k] for k in ('document_version_id','render_sha256','index_generation')};body['q']=f'Which figure explains the approach? R24 CPU region {name}.'
                r=client.post(url,json=body,headers=headers);check(name+'_fresh_Q_real_D_rank',r.status_code==200 and r.json()['status']=='ready' and bool(r.json()['items']))
                crop_url=r.json()['items'][0]['crop_url'];check(name+'_real_crop',client.get(crop_url).status_code==200)
                check(name+'_admin_no_private_region_bypass',admin.get(url+'/status').status_code==404)
                check(name+'_admin_no_private_crop_bypass',admin.get(crop_url).status_code==404)
                check(name+'_management_revoke',admin.post('/admin/users/'+uid+'/sessions/revoke',json={},headers=headers_admin).status_code==200)
                for label,path in (('search','/search?q=after-revoke'),('PNG',hit['preview_url']),('region-status',url+'/status'),('crop',crop_url)):
                    check(name+'_revoked_'+label,client.get(path).status_code==401)
                check(name+'_revoked_rank',client.post(url,json=body,headers=headers).status_code==401)
                login(client,name,passwords[name]);check(name+'_old_signature_not_reused',client.get(crop_url).status_code==404)
            check('upload_origin_still_protected',client.post('/index',files={'file':('probe.pdf',b'%PDF','application/pdf')},headers={'Origin':'https://bad.invalid'}).status_code==403)
        audits=[json.loads(p.read_text('utf-8')) for d in ('queries','regions') for p in (OUT/d).glob('*.json')]
        check('six_new_query_forwards_one_CPU_worker',len(audits)==6 and sorted(a['forward_count'] for a in audits)==list(range(1,7)) and len({a['worker_pid'] for a in audits})==1)
        check('no_model_network_and_frozen_profile',all(a['network_attempts']==0 and a['profile_sha256']==hashlib.sha256((ROOT/'configs/colpali_local.json').read_bytes()).hexdigest() for a in audits))
        save(OUT/'real.json',{'round':'R24','overall':'passed','checks':checks,'cases':cases,'actual_queries':6,'placement':'CPU BF16 exact original ColPali weights/implementation/profile; D CPU float32; formal GPU worker untouched',
            'region_audits':[{'cache_hit':a['regions']['cache_hit'],'d_forward_ms':a['regions']['d_forward_ms']} for a in audits if 'regions' in a],
            'limits':'Fresh ASGI with real SQLite, original query encoding, Qdrant and PNG/D/crop. Reuses R22 PDFs/features/candidates read-only; no new PDF/page encoding/MinerU, no GPU/browser/accuracy/capacity claim.'})
        print('R24 real CPU search/regions passed:',len(checks),'checks; 6 fresh queries')
    finally:
        worker.close();engine.dispose()
        for name in ('LAYOUTPATCH_QUERY_AUDIT_DIR','LAYOUTPATCH_REGION_AUDIT_DIR'):os.environ.pop(name,None)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','http','cli','real'));args=parser.parse_args()
    globals()[args.action]()
