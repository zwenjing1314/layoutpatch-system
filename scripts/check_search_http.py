"""Real HTTP/Next/Qdrant/GPU validation in an isolated database and unique collection.

Requires free ports 3000/8000 and a production frontend build. Only its own
processes and unique test collection are stopped/deleted; artifacts stay private.
"""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT, make_engine
from backend.db.models import User, Document, DocumentVersion, Page, IndexGeneration, IndexPage
from backend.db.seed import seed
from backend.search.indexing import import_features
from backend.search.qdrant import Qdrant, SearchUnavailable
from backend.search.scope import allowed_scope
from backend.search.settings import SearchSettings
from scripts.migrate_database import migrate


def main():
    for port in (3000,8000):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0:
                raise RuntimeError('Required port occupied; no existing process stopped')
    run_id=uuid.uuid4().hex[:12]
    folder=ROOT/'runtime/verification/r10'/('live-'+run_id)
    folder.mkdir(parents=True)
    audit_dir=folder/'queries'
    path=folder/'metadata.sqlite3'
    report={'date':'2026-11-07','round':'R10','scope':'isolated SQLite and unique real Qdrant collection; real Next/Uvicorn and ColPali GPU',
            'checks':[],'run_directory':folder.relative_to(ROOT).as_posix(),'failures':[]}
    def check(name,passed):
        report['checks'].append({'name':name,'passed':bool(passed)})
        if not passed: raise AssertionError(name)
    processes=[]; streams=[]; clients=[]; cases=[]; collection=None
    qdrant=Qdrant()
    engine=make_engine(path)
    passwords={name:secrets.token_urlsafe(24) for name in ('A','B','admin')}
    headers={'Origin':'http://127.0.0.1:3000'}
    env={**os.environ,'LAYOUTPATCH_DATABASE_PATH':str(path),'APP_ORIGIN':headers['Origin'],
         'SESSION_COOKIE_SECURE':'false','LAYOUTPATCH_QUERY_AUDIT_DIR':str(audit_dir),'PYTHONUTF8':'1','NEXT_TELEMETRY_DISABLED':'1'}
    args=[sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--workers','1','--no-access-log']
    def launch(name,argv,cwd,environment):
        stream=(folder/(name+str(len(processes))+'.log')).open('w',encoding='utf-8')
        process=subprocess.Popen(argv,cwd=cwd,env=environment,stdout=stream,stderr=subprocess.STDOUT,
                                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        processes.append(process);streams.append(stream);return process
    def stop(process):
        if process.poll() is None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],check=True,capture_output=True)
            process.wait(timeout=15)
    def ready(url):
        for _ in range(100):
            try:
                if httpx.get(url,timeout=2,trust_env=False).status_code==200:return
            except httpx.HTTPError:pass
            time.sleep(.15)
        raise RuntimeError('Service startup failed')
    def audit_files(): return set(audit_dir.glob('*.json')) if audit_dir.exists() else set()
    def query(client,name,question,k=50):
        before=audit_files()
        response=client.get('/search',params={'q':question,'k':k})
        check(name+'_200',response.status_code==200)
        after=audit_files()-before
        check(name+'_one_new_forward',len(after)==1)
        audit=next(iter(after))
        data=json.loads(audit.read_text())
        check(name+'_offline_real_query',data['query_sha256']==hashlib.sha256(question.encode()).hexdigest() and data['network_attempts']==0)
        with Session(engine) as db:
            user=db.scalar(select(User).where(User.username==name.split('_')[0]))
            scope=allowed_scope(db,user)
            pages={p.id:db.get(Page,p.id).source_page_id for p in scope.pages}
        # Shared fixture has its own identity but duplicates a known test vector.
        pages={k:shared_source if v=='fixture-shared:p0' else v for k,v in pages.items()}
        cases.append({'name':name,'audit':str(audit),'pages':pages,'items':response.json()['items']})
        return response,data,scope
    shared_source=None
    try:
        migrate(path);seed(engine,passwords.__getitem__)
        with Session(engine) as db, db.begin():
            index=db.scalar(select(IndexGeneration))
            index.collection_name += '_r10test_'+run_id
            collection=index.collection_name
        check('test_collection_initially_absent',qdrant.info(collection) is None)
        first=import_features(engine,ROOT/'runtime/indexes/r10-features/manifest.json',qdrant)
        second=import_features(engine,ROOT/'runtime/indexes/r10-features/manifest.json',qdrant)
        check('import_13_full_pages',first['page_count']==13 and first['vector_count']==13403)
        check('repeat_verifies_without_upsert',second['existing_collection_verified_without_upsert'])
        print('Isolated index imported and repeat verified.',flush=True)
        backend=launch('backend',args,ROOT,env)
        ready('http://127.0.0.1:8000/health')
        launch('frontend',[shutil.which('node'),'node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3000'],ROOT/'frontend',env)
        ready('http://127.0.0.1:3000/api/health')
        for name in ('admin','A','B'):
            client=httpx.Client(base_url='http://127.0.0.1:3000/api',timeout=240,trust_env=False)
            clients.append(client)
            check(name+'_unauthenticated401',client.get('/search',params={'q':'new question'}).status_code==401)
            login=client.post('/auth/login',json={'username':name,'password':passwords[name]},headers=headers)
            check(name+'_login',login.status_code==200)
            check(name+'_first_password403',client.get('/search',params={'q':'new question'}).status_code==403)
            new=secrets.token_urlsafe(24)
            changed=client.post('/auth/password',json={'current_password':passwords[name],'new_password':new},headers={**headers,'X-CSRF-Token':login.json()['csrf_token']})
            check(name+'_change_password',changed.status_code==204)
            passwords[name]=new
            check(name+'_relogin',client.post('/auth/login',json={'username':name,'password':new},headers=headers).status_code==200)
        admin,a,b=clients
        empty=admin.get('/search',params={'q':'No private library yet'})
        check('admin_empty_without_gpu_or_qdrant_query',empty.status_code==200 and empty.json()['items']==[] and not audit_files())
        question_a='Where does the paper compare hardware area and energy for temporal unary matrix multiplication?'
        question_b='What does Frechet Music Distance measure when generated audio is compared with reference music?'
        ra,aa,sa=query(a,'A_hardware',question_a)
        rb,ab,sb=query(b,'B_music',question_b)
        cross,ac,sc=query(a,'A_music',question_b,k=3)
        repeat,ar,_=query(a,'A_repeat',question_a)
        check('private_counts_5_and_8',len(ra.json()['items'])==5 and len(rb.json()['items'])==8)
        check('private_ids_disjoint',not ({i['page_id'] for i in ra.json()['items']} & {i['page_id'] for i in rb.json()['items']}))
        check('same_worker_new_forward_each_time',len({v['worker_pid'] for v in (aa,ab,ac,ar)})==1 and [v['forward_count'] for v in (aa,ab,ac,ar)]==[1,2,3,4])
        cross_audit=json.loads(Path(cases[-2]['audit']).read_text())
        global_scope=replace(sa,pages=sa.pages+sb.pages)
        global_hits=qdrant.query(global_scope,cross_audit['vector'],1)
        check('more_relevant_b_excluded_before_a_topk',global_hits[0]['id'] in {p.id for p in sb.pages} and len(cross.json()['items'])==3)
        check('search_no_store',cross.headers.get('cache-control')=='private, no-store')
        check('client_cannot_supply_scope',a.get('/search',params={'q':'x','owner_id':'B'}).status_code==422)
        print('Real GPU private scope queries passed; adding separate shared fixture.',flush=True)
        # A/B private documents remain untouched. Create a distinct administrator
        # shared document/page identity in this isolated DB and test collection.
        original_points=qdrant.all_points(collection)
        with Session(engine) as db, db.begin():
            owner=db.scalar(select(User).where(User.username=='admin'))
            original=db.get(Page,str(original_points[0]['id']));version=db.get(DocumentVersion,original.document_version_id)
            shared_source=original.source_page_id
            doc=Document(source_key='fixture-shared',owner_id=owner.id,display_name='Shared fixture',visibility='shared',status='ready')
            db.add(doc);db.flush()
            ver=DocumentVersion(document_id=doc.id,version=1,pdf_sha256=version.pdf_sha256,pdf_path=version.pdf_path,page_count=1,
                                render_profile_json=version.render_profile_json,render_profile_sha256=version.render_profile_sha256)
            db.add(ver);db.flush();doc.active_version_id=ver.id
            page=Page(document_version_id=ver.id,source_page_id='fixture-shared:p0',page_index=0,width_px=original.width_px,height_px=original.height_px,
                      render_sha256=original.render_sha256,image_path=original.image_path)
            db.add(page);db.flush()
            index=db.scalar(select(IndexGeneration));index.page_count=14;index.vector_count=14*1031
            ip=db.get(IndexPage,(index.id,original.id))
            db.add(IndexPage(index_id=index.id,page_id=page.id,embedding_sha256=ip.embedding_sha256,token_count=1031))
            point={'id':page.id,'vector':original_points[0]['vector'],'payload':{'page_id':page.id,'document_id':doc.id,
                   'document_version_id':ver.id,'profile_id':index.profile_id,'index_generation':index.id,'owner_id':owner.id,
                   'visibility':'shared','render_sha256':page.render_sha256,'embedding_sha256':ip.embedding_sha256}}
            shared_id,shared_page=doc.id,page.id
            qdrant.upsert(collection,[point])
        for name,client,count in [('A',a,6),('B',b,9),('admin',admin,1)]:
            r,_,_=query(client,name+'_shared',question_a)
            check(name+'_shared_separate_count',len(r.json()['items'])==count and shared_page in {i['page_id'] for i in r.json()['items']})
        with Session(engine) as db,db.begin():db.get(Document,shared_id).visibility='private'
        withdrawn,_,_=query(a,'A_withdrawn',question_a)
        check('withdrawal_uses_sql_not_stale_qdrant_visibility',shared_page not in {i['page_id'] for i in withdrawn.json()['items']})
        token=a.cookies.get('layoutpatch_session')
        me=a.get('/auth/me').json()
        check('logout204',a.post('/auth/logout',headers={**headers,'Content-Type':'application/json','X-CSRF-Token':me['csrf_token']}).status_code==204)
        check('old_cookie_search401',a.get('/search',params={'q':'new query'},headers={'Cookie':'layoutpatch_session='+token}).status_code==401)
        # Kill this test backend's own model child, not an unrelated GPU process.
        os.kill(aa['worker_pid'],signal.SIGTERM)
        dead=b.get('/search',params={'q':'Model failure must be explicit'})
        check('stopped_real_model503',dead.status_code==503 and dead.json().get('detail')=='SEARCH_UNAVAILABLE')
        # Restart the test backend with an unused local Qdrant port; persistent
        # auth survives, but search must fail rather than return an empty result.
        stop(backend)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); unused=sock.getsockname()[1]
        backend=launch('backend-fault',args,ROOT,{**env,'QDRANT_URL':f'http://127.0.0.1:{unused}'})
        ready('http://127.0.0.1:8000/health')
        check('session_persists_backend_restart',b.get('/auth/me').status_code==200)
        unavailable=b.get('/search',params={'q':'Qdrant failure must be explicit'})
        check('real_qdrant_connection_failure503',unavailable.status_code==503 and unavailable.json().get('detail')=='SEARCH_UNAVAILABLE')
        stop(backend)
        reference_path=folder/'reference-input.json'
        reference_path.write_text(json.dumps(cases,indent=2),encoding='utf-8')
        reference=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-B','-u','scripts/check_search_reference.py','--input',str(reference_path)],cwd=ROOT,env={**os.environ,'PYTHONUTF8':'1'},capture_output=True,timeout=120)
        (folder/'reference.log').write_bytes(reference.stdout+reference.stderr)
        check('official_cpu_reference_passed',reference.returncode==0)
        report['query_forwards']=len(audit_files())
        report['initial_index']=first
        report['overall']='passed'
    except Exception as error:
        report['overall']='failed';report['failures'].append(type(error).__name__+': '+str(error)[:300])
        raise
    finally:
        for process in processes:stop(process)
        for client in clients:client.close()
        for stream in streams:stream.close()
        engine.dispose()
        if collection and '_r10test_'+run_id in collection:
            qdrant.request('DELETE',qdrant.path(collection))
            report['unique_test_collection_removed']=qdrant.info(collection) is None
        (ROOT/'docs/checks/stage1b-4-http.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
