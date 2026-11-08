"""R22 actual HTTP session/restart checks, only isolated DB and random credentials."""
import argparse
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.db.connection import ROOT,make_engine
from backend.db.models import AuthSession,User,Document,PageParse
from scripts.check_regions import OUT,STATE,DATABASE,ORIGIN,read
from scripts.check_regions_http import save


def main(action):
    evidence=read(OUT/'http-current.json');private=OUT/'recovery-private.json';checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        save(OUT/f'recovery-{action}-checks.json',checks)
        if not value:raise AssertionError(name)
    base='http://127.0.0.1:8000'
    if action=='before':
        selected=read(STATE);kept=[]
        for owner in ('A','B'):
            case=next(r for r in evidence['regions'] if r['owner']==owner)
            with httpx.Client(base_url=base,timeout=235,trust_env=False) as c:
                login=c.post('/auth/login',json={'username':owner,'password':selected['passwords'][owner]},headers={'Origin':ORIGIN})
                check(owner+'_recovery_login',login.status_code==200)
                headers={'Origin':ORIGIN,'X-CSRF-Token':login.json()['csrf_token']}
                url='/pages/'+case['hit']['page_id']+'/regions'
                ranked=c.post(url,json=case['action'],headers=headers)
                check(owner+'_same_real_input_before_restart',ranked.status_code==200 and ranked.json()['status']=='ready')
                crop=ranked.json()['items'][0]['crop_url']
                check(owner+'_crop_before_restart',c.get(crop).status_code==200)
                kept.append({'owner':owner,'cookies':dict(c.cookies),'headers':headers,'case':case,'crop_url':crop})
        save(private,kept)
    else:
        engine=make_engine(DATABASE)
        for data in read(private):
            owner=data['owner'];case=data['case'];url='/pages/'+case['hit']['page_id']+'/regions'
            with httpx.Client(base_url=base,timeout=235,trust_env=False,cookies=data['cookies'],headers=data['headers']) as c:
                check(owner+'_session_persisted_restart',c.get('/auth/me').status_code==200)
                check(owner+'_status_ready_restart',c.get(url+'/status').json()['status']=='ready')
                check(owner+'_crop_same_cookie_restart',c.get(data['crop_url']).status_code==200)
                check(owner+'_PNG_restart',c.get(case['preview_url']).status_code==404) # Different prior session token cannot be replayed.
                # HTTP fixtures are isolated, explicit, reversible and cannot be mistaken for model failures.
                with Session(engine) as db,db.begin():
                    record=db.get(PageParse,(case['response']['task_id'],case['hit']['page_id']));saved=(record.status,record.error_code);record.status='no_candidates';record.error_code=None
                try:
                    r=c.post(url,json=case['action']);check(owner+'_no_candidates_HTTP',r.status_code==200 and r.json()['status']=='no_candidates' and not r.json()['items'])
                finally:
                    with Session(engine) as db,db.begin():record=db.get(PageParse,(case['response']['task_id'],case['hit']['page_id']));record.status,record.error_code=saved
                with Session(engine) as db,db.begin():
                    u=db.scalar(select(User).where(User.username==owner));sessions=list(db.scalars(select(AuthSession).where(AuthSession.user_id==u.id)))
                    for row in sessions:row.revoked_at=1
                for method,path,kwargs in [('GET',url+'/status',{}),('POST',url,{'json':case['action']}),('GET',data['crop_url'],{})]:
                    r=c.request(method,path,**kwargs);check(owner+'_revoked_'+method+path.split('?')[0],r.status_code==401 and 'no-store' in r.headers.get('cache-control',''))
                # A fresh same-user session still cannot reuse the old crop signature.
                creds=read(STATE)['passwords'];login=c.post('/auth/login',json={'username':owner,'password':creds[owner]},headers={'Origin':ORIGIN})
                check(owner+'_fresh_same_user_crop_not_replayable',login.status_code==200 and c.get(data['crop_url']).status_code==404)
        engine.dispose()
        first=evidence['regions'][0];url='/pages/'+first['hit']['page_id']+'/regions'
        with httpx.Client(base_url=base,trust_env=False,headers={'Origin':ORIGIN}) as c:
            for method,path,kwargs in [('GET',url+'/status',{}),('POST',url,{'json':first['action']}),('GET',first['response']['items'][0]['crop_url'],{})]:
                r=c.request(method,path,**kwargs);check('anonymous_'+method+path.split('?')[0],r.status_code==401 and 'no-store' in r.headers.get('cache-control',''))
    save(ROOT/f'docs/checks/stage2-6-recovery-{action}.json',{'round':'R22','overall':'passed','checks':checks,'fixture':'Only after step changes no_candidates flags and restores; session revocation isolated. Restart is actual identity-guarded process stop/start.'})
    print(action,len(checks),'checks passed; credentials not exported')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['before','after']);main(p.parse_args().action)
