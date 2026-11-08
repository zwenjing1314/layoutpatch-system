"""Actual localhost HTTP, original ColPali queries/Qdrant and private PNGs after parsing."""
import json
import os
import socket
import subprocess
import sys
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT,make_engine
from backend.db.models import Document,PageParse,ParsingTask
from backend.db.seed import sha
from backend.documents.previews import preview_token
from scripts.check_stage1b_acceptance import process_records
from scripts.check_parsing import OUT,STATE,DATABASE,read,write,ORIGIN


def main():
    state=read(STATE)
    attempt=1
    while (OUT/f'http-attempt{attempt}').exists():attempt+=1
    run_dir=OUT/f'http-attempt{attempt}';run_dir.mkdir()
    engine=make_engine(DATABASE)
    with Session(engine) as db:
        for selected in state['selected']:
            task=db.scalar(select(ParsingTask).where(ParsingTask.document_version_id==selected['version_id']).order_by(ParsingTask.created_at.desc()).limit(1))
            if not task or task.status!='ready':raise RuntimeError('Current real PDF parsing not ready')
    engine.dispose()
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',8001))==0:raise RuntimeError('8001 occupied, refusing replacement')
    env={k:v for k,v in os.environ.items() if not k.startswith('LAYOUTPATCH_')}
    env.update(PYTHONUTF8='1',APP_ORIGIN=ORIGIN,SESSION_COOKIE_SECURE='false')
    with (run_dir/'isolated-http.log').open('xb') as log:
        process=subprocess.Popen([sys.executable,'-m','uvicorn','scripts.parsing_acceptance_server:app','--host','127.0.0.1','--port','8001','--workers','1','--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    owned=process_records('ProcessId='+str(process.pid))[0]
    write(run_dir/'http-process.json',owned)
    checks=[];hits=[]
    def check(name,condition,**detail):
        checks.append({'name':name,'passed':bool(condition),**detail})
        if not condition:raise AssertionError(name)
    try:
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            try:
                if httpx.get('http://127.0.0.1:8001/health',trust_env=False,timeout=2).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.2)
        else:raise RuntimeError('Isolated HTTP startup timed out')
        with httpx.Client(base_url='http://127.0.0.1:8001',trust_env=False,timeout=230) as client:
            a,b=state['selected']
            response=client.get(f"/documents/{a['document_id']}/parsing")
            check('anonymous_status_401_no_store',response.status_code==401 and 'no-store' in response.headers.get('cache-control',''))
            for owner in ('A','B'):
                selected=next(x for x in state['selected'] if x['owner']==owner)
                other=next(x for x in state['selected'] if x['owner']!=owner)
                response=client.post('/auth/login',json={'username':owner,'password':state['passwords'][owner]},headers={'Origin':ORIGIN})
                check(owner+'_isolated_login',response.status_code==200)
                csrf=response.json()['csrf_token'];headers={'Origin':ORIGIN,'X-CSRF-Token':csrf}
                url=f"/documents/{selected['document_id']}/parsing"
                current=client.get(url)
                check(owner+'_real_ready_status_page_identity',current.status_code==200 and current.json()['status']=='ready' and [p['page_index'] for p in current.json()['pages']]==list(range(selected['pages'])))
                check(owner+'_no_private_parser_paths_text_or_candidates',all(k not in current.text for k in ('candidates_json','pdf_path','raw_path','native_PDF')))
                check(owner+'_other_private_status_404',client.get(f"/documents/{other['document_id']}/parsing").status_code==404)
                check(owner+'_csrf_required',client.post(url,json={},headers={'Origin':ORIGIN}).status_code==403)
                check(owner+'_origin_required',client.post(url,json={},headers={'Origin':'https://bad.invalid','X-CSRF-Token':csrf}).status_code==403)
                repeated=client.post(url,json={},headers=headers)
                check(owner+'_same_ready_task_is_idempotent',repeated.status_code==202 and repeated.json()['task_id']==current.json()['task_id'])
                for mode in ('library','document'):
                    response=client.get('/search',params={'q':f'Which figures and tables compare the proposed method with previous results? {owner} {mode}', 'k':3,**({'document_id':selected['document_id']} if mode=='document' else {})})
                    check(owner+'_'+mode+'_real_search_after_parse',response.status_code==200 and len(response.json()['items'])>0)
                    check(owner+'_'+mode+'_same_scope_identity',response.json()['search_mode']==mode and all(i['document_id']==selected['document_id'] for i in response.json()['items']) if mode=='document' else response.json()['search_mode']=='library')
                    for i,item in enumerate(response.json()['items']):
                        image=client.get(item['preview_url'])
                        check(owner+'_'+mode+f'_PNG{i}_verified',image.status_code==200 and sha(image.content)==item['render_sha256'] and image.headers.get('content-type')=='image/png')
                    hits.append({'owner':owner,'mode':mode,'items':[{key:item[key] for key in ('document_id','document_version_id','page_id','page_index','render_sha256','page_score')} for item in response.json()['items']]})
                # Make only this isolated task fail. Retrieval state and signed image remain actual.
                engine=make_engine(DATABASE)
                with Session(engine) as db,db.begin():
                    task=db.get(ParsingTask,current.json()['task_id']);task.status='failed';task.error_code='R20_EXPLICIT_PARSE_FAILURE_FIXTURE'
                failed=client.get(url)
                check(owner+'_parse_failure_visible',failed.json()['status']=='failed')
                response=client.get('/search',params={'q':f'Where are the quantitative evaluation results shown? {owner}','k':1,'document_id':selected['document_id']})
                check(owner+'_real_search_still_works_when_parse_failed',response.status_code==200 and len(response.json()['items'])==1)
                image=client.get(response.json()['items'][0]['preview_url'])
                check(owner+'_real_image_still_works_when_parse_failed',image.status_code==200)
                with Session(engine) as db,db.begin():
                    task=db.get(ParsingTask,current.json()['task_id']);task.status='ready';task.error_code=None
                engine.dispose()
                check(owner+'_logout',client.post('/auth/logout',json={},headers=headers).status_code==204)
                check(owner+'_status_after_logout_401',client.get(url).status_code==401)
            response=client.post('/auth/login',json={'username':'admin','password':state['passwords']['admin']},headers={'Origin':ORIGIN})
            check('admin_has_no_private_status_bypass',client.get(f"/documents/{a['document_id']}/parsing").status_code==404)
        write(ROOT/'docs/checks/stage2-4-http.json',{'round':'R20','overall':'passed','checks':checks,'hits':hits,'notes':['6 real queries; task failed flag injection is explicit and restored; failed parser worker exceptions/timeouts are independently tested','No model benchmark/accuracy claim; no page encoding or D execution']})
        print(f'{len(checks)} actual HTTP checks passed;6 real original-model queries')
    except Exception:
        write(run_dir/'failed-checks.json',{'checks':checks,'hits':hits})
        raise
    finally:
        current=process_records('ProcessId='+str(process.pid))
        if current and current!=[owned]:raise RuntimeError('HTTP test process identity changed; refusing stop')
        if current:subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,check=True)


if __name__=='__main__':main()
