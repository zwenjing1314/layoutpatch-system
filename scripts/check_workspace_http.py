"""R11 real proxy/image checks. Prepare an isolated DB, run services, then check.

The live browser uses the same isolated services. Credentials and preview URLs
stay in ignored runtime; reports contain booleans/counts only. No formal mutation.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT, make_engine
from backend.db.models import AuthSession, Document, DocumentVersion, IndexGeneration, Page, User
from backend.db.seed import seed
from backend.auth.store import digest
from backend.documents.previews import preview_url
from backend.search.indexing import import_features
from backend.search.qdrant import Qdrant
from scripts.migrate_database import migrate

STATE = ROOT / 'runtime/verification/r11/workspace-state.json'
REPORT = ROOT / 'docs/checks/stage1b-5-http.json'
ORIGIN = 'http://127.0.0.1:3000'


def save(data): STATE.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def prepare():
    if STATE.exists(): raise RuntimeError('Existing R11 state; inspect and reuse or clean it first')
    folder=ROOT/'runtime/verification/r11'/('live-'+uuid.uuid4().hex[:12]);folder.mkdir()
    database=folder/'metadata.sqlite3';migrate(database)
    passwords={name:secrets.token_urlsafe(24) for name in ('A','B','admin')}
    engine=make_engine(database)
    try:
        seed(engine,passwords.__getitem__)
        with Session(engine) as db,db.begin():
            index=db.scalar(select(IndexGeneration));index.collection_name += '_r11test_'+uuid.uuid4().hex[:12]
            collection=index.collection_name
        imported=import_features(engine,ROOT/'runtime/indexes/r10-features/manifest.json')
    finally:engine.dispose()
    save({'database':str(database),'folder':str(folder),'collection':collection,'passwords':passwords,
          'initial_page_count':imported['page_count'],'initial_vector_count':imported['vector_count']})
    print('Prepared isolated R11 DB and unique Qdrant collection; credentials kept private.')


def check():
    state=json.loads(STATE.read_text(encoding='utf-8'))
    report={'date':'2026-11-07','round':'R11','batch':'1B-5','checks':[],
            'scope':'real production Next + Uvicorn + Qdrant + original GPU; isolated DB/collection',
            'formal_password_changes':False}
    def verify(name,ok):
        report['checks'].append({'name':name,'passed':bool(ok)})
        if not ok:raise AssertionError(name)
    engine=make_engine(Path(state['database']))
    try:
        with httpx.Client(base_url=ORIGIN+'/api',timeout=240,trust_env=False) as client:
            headers={'Origin':ORIGIN,'Content-Type':'application/json'}
            verify('proxy_health',client.get('/health').status_code==200)
            verify('image_unauthenticated401',client.get('/pages/unknown/image').status_code==401)
            for name in ('A','B','admin'):
                login=client.post('/auth/login',json={'username':name,'password':state['passwords'][name]},headers=headers)
                verify(name+'_initial_login',login.status_code==200 and login.json()['must_change_password'])
                verify(name+'_first_change_image403',client.get('/pages/unknown/image').status_code==403)
                if name=='A':continue  # Browser inspects the actual initial-change page.
                new=secrets.token_urlsafe(24)
                changed=client.post('/auth/password',json={'current_password':state['passwords'][name],'new_password':new},
                                    headers={**headers,'X-CSRF-Token':login.json()['csrf_token']})
                verify(name+'_password_change204',changed.status_code==204)
                state['passwords'][name]=new;save(state)
                verify(name+'_new_login',client.post('/auth/login',json={'username':name,'password':new},headers=headers).status_code==200)
                if name=='admin':
                    response=client.get('/search',params={'q':'Which documents can I read?','k':3})
                    verify('admin_real_empty',response.status_code==200 and response.json()['items']==[])
            client.post('/auth/login',json={'username':'B','password':state['passwords']['B']},headers=headers)
            response=client.get('/search',params={'q':'How does Frechet Music Distance compare generated and reference music?','k':10})
            verify('B_real_query_eight_pages',response.status_code==200 and len(response.json()['items'])==8)
            hits=response.json()['items'];url=hits[0]['preview_url']
            state['B_preview_url']=url;save(state)
            for i,hit in enumerate(hits):
                image=client.get(hit['preview_url'])
                verify(f'B_png_{i+1}_identity',image.status_code==200 and hashlib.sha256(image.content).hexdigest()==hit['render_sha256'])
                verify(f'B_png_{i+1}_private_no_store',image.headers.get('cache-control')=='private, no-store' and image.headers.get('vary')=='Cookie')
            verify('preview_no_304_or_range_bypass',client.get(url,headers={'If-None-Match':'*','Range':'bytes=0-1'}).status_code==200)
            verify('bare_page_id404',client.get(url.split('?')[0]).status_code==404)
            verify('raw_files404',client.get('/files/anything.png').status_code==404)
            old=client.cookies.get('layoutpatch_session');csrf=client.get('/auth/me').json()['csrf_token']
            verify('logout204',client.post('/auth/logout',headers={**headers,'X-CSRF-Token':csrf}).status_code==204)
            verify('copied_cookie_image401',client.get(url,headers={'Cookie':'layoutpatch_session='+old}).status_code==401)
            client.cookies.clear()
            client.post('/auth/login',json={'username':'B','password':state['passwords']['B']},headers=headers)
            verify('same_user_new_session_old_url404',client.get(url).status_code==404)
            client.post('/auth/login',json={'username':'admin','password':state['passwords']['admin']},headers=headers)
            verify('admin_no_private_preview_bypass404',client.get(url).status_code==404)
            # Separate shared document for object authorization only; not indexed
            # and not part of a search while ready. A/B private docs unchanged.
            with Session(engine) as db,db.begin():
                source=db.get(Page,hits[0]['page_id']);version=db.get(DocumentVersion,source.document_version_id)
                admin=db.scalar(select(User).where(User.username=='admin'))
                doc=Document(source_key='r11-media-shared',owner_id=admin.id,display_name='Shared media fixture',visibility='shared',status='ready')
                db.add(doc);db.flush()
                ver=DocumentVersion(document_id=doc.id,version=1,pdf_sha256=version.pdf_sha256,pdf_path=version.pdf_path,page_count=1,
                    render_profile_json=version.render_profile_json,render_profile_sha256=version.render_profile_sha256)
                db.add(ver);db.flush();doc.active_version_id=ver.id
                page=Page(document_version_id=ver.id,source_page_id='r11-media-shared:p0',page_index=0,width_px=source.width_px,height_px=source.height_px,render_sha256=source.render_sha256,image_path=source.image_path)
                db.add(page);db.flush();shared_id,shared_doc,render=page.id,doc.id,page.render_sha256
            urls=[]
            for name in ('B','admin'):
                client.post('/auth/login',json={'username':name,'password':state['passwords'][name]},headers=headers)
                with Session(engine) as db:
                    row=db.get(AuthSession,digest(client.cookies.get('layoutpatch_session')))
                    shared_url=preview_url(row,shared_id,render)
                if urls:verify('shared_old_session_url404',client.get(urls[0]).status_code==404)
                verify(name+'_shared_media200',client.get(shared_url).status_code==200);urls.append(shared_url)
            with Session(engine) as db,db.begin():db.get(Document,shared_doc).visibility='private'
            client.post('/auth/login',json={'username':'B','password':state['passwords']['B']},headers=headers)
            with Session(engine) as db:
                row=db.get(AuthSession,digest(client.cookies.get('layoutpatch_session')))
                withdrawn_url=preview_url(row,shared_id,render)
            verify('shared_withdrawn404',client.get(withdrawn_url).status_code==404)
            with Session(engine) as db,db.begin():db.get(Document,shared_doc).status='registered'
            csrf=client.get('/auth/me').json()['csrf_token']
            client.post('/auth/logout',headers={**headers,'X-CSRF-Token':csrf})
        report['overall']='passed'
    except BaseException as error:
        report['overall']='failed';report['failure_type']=type(error).__name__
        raise
    finally:
        engine.dispose();REPORT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Passed '+str(len(report['checks']))+' real HTTP checks. Isolated services remain for browser QA.')


def change_a_for_browser():
    # Non-UI test action only: no real user credential, and no browser automation
    # submits a password change. Browser separately verifies gate and relogin.
    state=json.loads(STATE.read_text(encoding='utf-8'))
    with httpx.Client(base_url=ORIGIN+'/api',timeout=30,trust_env=False) as c:
        headers={'Origin':ORIGIN,'Content-Type':'application/json'}
        response=c.post('/auth/login',json={'username':'A','password':state['passwords']['A']},headers=headers)
        if response.status_code!=200:raise RuntimeError('Isolated A login failed')
        new=secrets.token_urlsafe(24)
        response=c.post('/auth/password',json={'current_password':state['passwords']['A'],'new_password':new},headers={**headers,'X-CSRF-Token':response.json()['csrf_token']})
        if response.status_code!=204:raise RuntimeError('Isolated A API change failed')
        state['passwords']['A']=new;state['A_password_changed_via']='isolated HTTP API, not browser submit';save(state)
    print('Isolated A credential changed via API; formal accounts untouched.')


def cleanup():
    state=json.loads(STATE.read_text(encoding='utf-8'))
    collection=state['collection']
    if '_r11test_' not in collection:raise RuntimeError('Refusing unrelated collection')
    q=Qdrant();q.request('DELETE',q.path(collection))
    if q.info(collection) is not None:raise RuntimeError('Test collection still present')
    state['test_collection_removed']=True;save(state)
    print('Removed only this R11 test collection; retained private evidence files.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','check','change-a','cleanup'])
    {'prepare':prepare,'check':check,'change-a':change_a_for_browser,'cleanup':cleanup}[parser.parse_args().action]()
