"""R22 resumable real new-PDF pipeline; private cookie/password state never printed."""
import json
from io import BytesIO
import math
from pathlib import Path
import time
from uuid import uuid4

import httpx
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT,make_engine
from backend.db.models import Document,Page,PageFeature,PageParse,ParsingTask
from backend.db.seed import sha
from scripts.check_regions import OUT,STATE,DATABASE,ORIGIN,read


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    state=read(STATE);attempt=1
    while (OUT/f'http-attempt{attempt}').exists():attempt+=1
    run=OUT/f'http-attempt{attempt}';run.mkdir()
    checks=[];cases=[];regions=[];reference=[]
    def check(name,value,**detail):
        checks.append({'name':name,'passed':bool(value),**detail})
        save(run/'checks.json',checks)
        if not value:raise AssertionError(name)
    def wait(client,path,terminal,seconds=1200):
        deadline=time.monotonic()+seconds;last=None
        while time.monotonic()<deadline:
            response=client.get(path);response.raise_for_status();data=response.json()
            if (data['status'],data.get('stage'),data.get('progress'))!=last:
                last=(data['status'],data.get('stage'),data.get('progress'));print(path.split('/')[1],last,flush=True)
            if data['status'] in terminal:return data
            time.sleep(2)
        raise TimeoutError(path)
    clients={}
    try:
        for owner in ('A','B','admin'):
            c=httpx.Client(base_url='http://127.0.0.1:8001',timeout=235,trust_env=False)
            result=c.post('/auth/login',json={'username':owner,'password':state['passwords'][owner]},headers={'Origin':ORIGIN})
            check(owner+'_isolated_login',result.status_code==200)
            c.headers.update({'Origin':ORIGIN,'X-CSRF-Token':result.json()['csrf_token']});clients[owner]=c
        for spec in state['selected']:
            c=clients[spec['owner']]
            if 'job_id' not in spec:
                spec['upload_id']=spec.get('upload_id',str(uuid4()));save(STATE,state)
                with Path(spec['path']).open('rb') as stream:
                    response=c.post('/index',files={'file':('R22同名完整文档.pdf',stream,'application/pdf')},headers={'X-Upload-ID':spec['upload_id']})
                check(spec['owner']+'_new_complete_upload_202',response.status_code==202)
                job=response.json();spec.update({key:job[key] for key in ('job_id','document_id','document_version_id')});save(STATE,state)
            result=wait(c,'/jobs/'+spec['job_id'],{'completed','failed','interrupted','cancelled'})
            save(run/(spec['owner']+'-job.json'),result)
            check(spec['owner']+'_all_pages_ingested',result['status']=='completed' and result['page_count']==spec['pages'],status=result['status'],error=result.get('error_code'))
            doc=c.get('/documents/'+spec['document_id']).json()
            check(spec['owner']+'_private_version1_pdf_sha',doc['visibility']=='private' and doc['version']==1 and doc['pdf_sha256']==spec['sha256'])
            response=c.post('/documents/'+spec['document_id']+'/parsing',json={})
            check(spec['owner']+'_explicit_parse202',response.status_code==202)
            parsed=wait(c,'/documents/'+spec['document_id']+'/parsing',{'ready','partial','failed','interrupted'})
            save(run/(spec['owner']+'-parse.json'),parsed);spec['task_id']=parsed['task_id'];save(STATE,state)
            check(spec['owner']+'_real_MinerU_all_pages',parsed['status']=='ready' and len(parsed['pages'])==spec['pages'] and all(p['status'] in {'ready','no_candidates'} for p in parsed['pages']),status=parsed['status'],errors=[p['error_code'] for p in parsed['pages'] if p['error_code']])
        engine=make_engine(DATABASE)
        for spec in state['selected']:
            owner=spec['owner'];c=clients[owner];other=clients['B' if owner=='A' else 'A']
            for mode in ('document','library'):
                q=('How is epsilon fairness defined and compared with equal treatment?' if owner=='A' else 'Which algorithm computes Kendall correlation efficiently and how is its complexity evaluated?')+' '+mode
                response=c.get('/search',params={'q':q,'k':3,**({'document_id':spec['document_id']} if mode=='document' else {})})
                check(owner+'_'+mode+'_real_search',response.status_code==200 and len(response.json().get('items',[]))==3)
                result=response.json();save(run/(owner+'-'+mode+'-search.json'),result)
                check(owner+'_'+mode+'_scope',result['search_mode']==mode and (mode=='library' or all(i['document_id']==spec['document_id'] for i in result['items'])))
                cases.append({'owner':owner,'mode':mode,'q':q,'response':result})
                with Session(engine) as db:
                    pages=db.scalars(select(Page).join(Document,Document.active_version_id==Page.document_version_id).where(Document.id==spec['document_id'] if mode=='document' else Document.owner_id==db.get(Document,spec['document_id']).owner_id)).all()
                    features={p.id:db.get(PageFeature,p.id) for p in pages}
                    mapping={p.id:({'tensor_path':features[p.id].tensor_path} if features[p.id] else {'source_page_id':p.source_page_id}) for p in pages}
                audit=next(p for p in (OUT/'query').glob('*.json') if read(p).get('query_sha256')==sha(q.encode()))
                reference.append({'name':owner+'_'+mode,'target_document_id':result['document_id'],'audit':str(audit),'pages':mapping,'items':result['items'],'k':3})
                # Document mode always tests a new page with complete features and real candidates.
                if mode!='document':continue
                for j,hit in enumerate(result['items']):
                    image=c.get(hit['preview_url'])
                    check(owner+f'_new_top{j+1}_PNG',image.status_code==200 and sha(image.content)==hit['render_sha256'])
                    status=c.get('/pages/'+hit['page_id']+'/regions/status')
                    check(owner+f'_status{j}_same_page',status.status_code==200 and status.json()['render_sha256']==hit['render_sha256'])
                    action={'q':q,'document_version_id':hit['document_version_id'],'render_sha256':hit['render_sha256'],'index_generation':result['index_generation']}
                    endpoint='/pages/'+hit['page_id']+'/regions'
                    check(owner+f'_other_status{j}_404',other.get(endpoint+'/status').status_code==404)
                    check(owner+f'_other_regions{j}_404',other.post(endpoint,json=action).status_code==404)
                    if status.json()['status']=='no_candidates':continue
                    ranked=c.post(endpoint,json=action)
                    check(owner+f'_real_D_top{j+1}',ranked.status_code==200 and ranked.json()['status']=='ready',code=ranked.status_code,state=ranked.json().get('status'),error=ranked.json().get('error_code'))
                    data=ranked.json();save(run/(owner+f'-regions-{j}.json'),data)
                    check(owner+f'_region_ids_types_scores{j}',all(r['candidate_id']==hit['page_id']+':block:'+str(r['layout_id']) and r['rank']==n+1 and math.isfinite(r['score']) for n,r in enumerate(data['items'])))
                    crop=c.get(data['items'][0]['crop_url']);box=data['items'][0]['bbox']
                    check(owner+f'_crop{j}_pixels',crop.status_code==200 and Image.open(BytesIO(crop.content)).size==(math.ceil(box[2])-math.floor(box[0]),math.ceil(box[3])-math.floor(box[1])))
                    (run/(owner+f'-crop-{j}.png')).write_bytes(crop.content)
                    check(owner+f'_other_crop{j}_404',other.get(data['items'][0]['crop_url']).status_code==404)
                    check(owner+f'_admin_crop{j}_404',clients['admin'].get(data['items'][0]['crop_url']).status_code==404)
                    check(owner+f'_crop{j}_no_store','no-store' in crop.headers.get('cache-control',''))
                    check(owner+f'_tamper_crop{j}_404',c.get(data['items'][0]['crop_url']+'0').status_code==404)
                    wrong={**action,'render_sha256':'0'*64}
                    check(owner+f'_stale_render{j}_409',c.post(endpoint,json=wrong).status_code==409)
                    check(owner+f'_origin{j}_403',c.post(endpoint,json=action,headers={'Origin':'https://bad.invalid'}).status_code==403)
                    check(owner+f'_csrf{j}_403',c.post(endpoint,json=action,headers={'X-CSRF-Token':'bad'}).status_code==403)
                    regions.append({'owner':owner,'hit':hit,'action':action,'response':data,'preview_url':hit['preview_url']})
            # Explicit parser status fixture; it cannot change retrieval/image readiness.
            first=next(r for r in regions if r['owner']==owner)
            with Session(engine) as db,db.begin():
                task=db.get(ParsingTask,spec['task_id']);old_status=task.status;task.status='failed';task.error_code='R22_EXPLICIT_PARSE_FAILURE_FIXTURE'
            try:
                path='/pages/'+first['hit']['page_id']+'/regions'
                failure=c.post(path,json=first['action'])
                check(owner+'_parse_failure_no_fake_regions',failure.status_code==200 and failure.json()['status']=='failed' and failure.json()['items']==[])
                check(owner+'_parse_failure_original_png',c.get(first['preview_url']).status_code==200)
            finally:
                with Session(engine) as db,db.begin():
                    task=db.get(ParsingTask,spec['task_id']);task.status=old_status;task.error_code=None
        engine.dispose()
        save(run/'regions.json',regions);save(run/'search-cases.json',cases);save(run/'reference-input.json',reference)
        save(OUT/'http-current.json',{'run':str(run),'regions':regions,'search_cases':cases})
        save(ROOT/'docs/checks/stage2-6-http.json',{'round':'R22','overall':'passed','checks':checks,'run':run.relative_to(ROOT).as_posix(),'real_new_pages':23,'new_queries':4,'real_region_requests':len(regions),'limits':'Parser failed flags explicitly injected then restored. No accuracy claim. Browser/restart/session revocation separate.'})
        print('PASSED',len(checks),'checks; actual new complete PDFs/pages=2/23; real regional pages=',len(regions),flush=True)
    finally:
        for c in clients.values():c.close()


if __name__=='__main__':main()
