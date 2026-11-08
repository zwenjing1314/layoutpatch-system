"""Actual old page-search/PNG chain with new worker code, isolated accounts only."""
import hashlib
import json
import os
import secrets

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.settings import AuthSettings
from backend.db.connection import ROOT,make_engine
from backend.db.models import Document,Page,User
from backend.db.seed import password_hasher
from backend.main import create_app

OUT=ROOT/'runtime/verification/r21'


def main():
    database=OUT/'metadata.sqlite3';engine=make_engine(database)
    passwords={name:secrets.token_urlsafe(24) for name in ('A','B','admin')}
    with Session(engine) as db,db.begin():
        for user in db.scalars(select(User)):user.password_hash=password_hasher.hash(passwords[user.username])
    os.environ['LAYOUTPATCH_QUERY_AUDIT_DIR']=str(OUT/'search-queries')
    app=create_app(AuthSettings(database=database));checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        assert value,name
    try:
        with TestClient(app) as client:
            for name in ('A','B'):
                response=client.post('/auth/login',json={'username':name,'password':passwords[name]},headers={'Origin':'http://127.0.0.1:3000'})
                check(name+'_isolated_login',response.status_code==200)
                doc=next(p['result']['identity']['document_id'] for p in json.loads((ROOT/'docs/checks/stage2-5-real.json').read_text())['pages'] if p['owner']==name)
                for mode in ('library','document'):
                    response=client.get('/search',params={'q':f'What does the main figure explain? R21 old chain {name} {mode}.','k':3,**({'document_id':doc} if mode=='document' else {})})
                    check(name+'_'+mode+'_real_search',response.status_code==200)
                    data=response.json();check(name+'_'+mode+'_mode',data['search_mode']==mode and bool(data['items']))
                    check(name+'_'+mode+'_regions_still_not_requested',all(i['region_status']=='not_requested' for i in data['items']))
                    with Session(engine) as db:
                        user=db.scalar(select(User).where(User.username==name))
                        allowed={p.id for p in db.scalars(select(Page).join(Document,Document.active_version_id==Page.document_version_id).where(Document.owner_id==user.id,Document.status=='ready'))}
                    check(name+'_'+mode+'_authorized_page_ids',all(i['page_id'] in allowed for i in data['items']))
                    if mode=='document':check(name+'_document_single_target',all(i['document_id']==doc for i in data['items']))
                    image=client.get(data['items'][0]['preview_url'])
                    check(name+'_'+mode+'_real_png',image.status_code==200 and hashlib.sha256(image.content).hexdigest()==data['items'][0]['render_sha256'])
                    check(name+'_'+mode+'_no_store',response.headers['cache-control']=='private, no-store' and image.headers['cache-control']=='private, no-store')
                client.post('/auth/logout',json={},headers={'Origin':'http://127.0.0.1:3000','X-CSRF-Token':client.get('/auth/me').json()['csrf_token']})
            check('anonymous_search',client.get('/search',params={'q':'test'}).status_code==401)
            check('origin_still_protected',client.post('/index',files={'file':('probe.pdf',b'%PDF-probe','application/pdf')},headers={'Origin':'https://bad.invalid'}).status_code==403)
        audits=[json.loads(p.read_text()) for p in (OUT/'search-queries').glob('*.json')]
        check('four_actual_original_query_forwards',len(audits)==4 and {a['forward_count'] for a in audits}=={1,2,3,4})
        check('original_encoder_and_no_network',all(a['network_attempts']==0 and a['profile_sha256']==hashlib.sha256((ROOT/'configs/colpali_local.json').read_bytes()).hexdigest() for a in audits))
        report={'round':'R21','overall':'passed','checks':checks,'actual_queries':4,'worker_pids':sorted({a['worker_pid'] for a in audits}),
            'scope':'Real TestClient ASGI requests in isolated R21 clone, real ColPali/Qdrant/PNG; not localhost TCP/browser or region HTTP checks; formal credentials unused'}
        with (ROOT/'docs/checks/stage2-5-search.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
        print(f'{len(checks)} actual ASGI search/protection checks passed; 4 real queries')
    finally:
        engine.dispose();os.environ.pop('LAYOUTPATCH_QUERY_AUDIT_DIR',None)


if __name__=='__main__':main()
