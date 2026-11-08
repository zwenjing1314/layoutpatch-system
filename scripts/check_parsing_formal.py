"""R20 guarded service restart and additive0008 migration, never authenticate formal users."""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time

import httpx

from backend.db.connection import ROOT, DEFAULT_DATABASE
from scripts.check_stage1b_acceptance import process_records, vector_fingerprint
from scripts.check_stage2_preflight import snapshot
from scripts.check_parsing import OUT, read, write
from scripts.migrate_database import migrate

OWNED=OUT/'service-ownership.json'


def stop_services():
    previous=read(ROOT/'runtime/verification/r19/ui/state.json')['owned']
    saved={}
    for name,expected in (('backend','-m uvicorn backend.main:app'),('frontend','node_modules/next/dist/bin/next start')):
        record=previous[name]
        current=process_records('ProcessId='+str(record['pid']))
        if len(current)!=1 or current[0]['Created']!=record['created'] or expected not in current[0]['CommandLine']:
            raise RuntimeError('Service ownership changed; refusing stop: '+name)
        saved[name]=current[0]
    write(OUT/'services-before.json',saved)
    for name in ('backend','frontend'):
        # Recheck immediately before each destructive process action.
        current=process_records('ProcessId='+str(saved[name]['ProcessId']))
        if current!=[saved[name]]:raise RuntimeError('Service changed before stop')
        subprocess.run(['taskkill','/PID',str(saved[name]['ProcessId']),'/T','/F'],check=True,capture_output=True)
    write(OWNED,{})
    print('Stopped only the two identity-verified project service trees; Qdrant untouched')


def migration():
    before=read(ROOT/'docs/checks/stage2-4-preflight.json')['database']
    current=snapshot(DEFAULT_DATABASE)
    if current!=before:raise RuntimeError('Formal database changed since baseline; inspect before migration')
    migrate(DEFAULT_DATABASE)
    after=snapshot(DEFAULT_DATABASE)
    checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value:raise AssertionError(name)
    check('0008_head',after['revision']=='0008_parsing')
    for table,value in before['tables'].items():
        if table!='alembic_version':check('unchanged_'+table,after['tables'][table]==value)
    check('only_three_additive_tables',set(after['tables'])-set(before['tables'])=={'parser_profiles','parsing_tasks','page_parses'})
    check('no_fabricated_parse_backfill',all(after['tables'][t]['count']==0 for t in ('parser_profiles','parsing_tasks','page_parses')))
    check('integrity_and_fk',after['integrity']=='ok' and after['foreign_key_errors']==0)
    migrate(DEFAULT_DATABASE);check('repeat_migration_unchanged',snapshot(DEFAULT_DATABASE)==after)
    baseline=read(ROOT/'docs/checks/stage2-4-preflight.json')
    check('original13_full_qdrant_unchanged',vector_fingerprint(baseline['collection'])==baseline['qdrant'])
    write(ROOT/'docs/checks/stage2-4-migration.json',{'round':'R20','overall':'passed','before':before,'after':after,'checks':checks})
    print(f'{len(checks)} formal additive-migration checks passed')


def start_services():
    owned=read(OWNED)
    env={k:v for k,v in os.environ.items() if not k.startswith('LAYOUTPATCH_')}
    env.update(PYTHONUTF8='1',APP_ORIGIN='http://127.0.0.1:3000',SESSION_COOKIE_SECURE='false',NEXT_TELEMETRY_DISABLED='1')
    for name,port,args,cwd,url in (
        ('backend',8000,[sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--workers','1','--no-access-log'],ROOT,'http://127.0.0.1:8000/health'),
        ('frontend',3000,[shutil.which('node'),'node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3000'],ROOT/'frontend','http://127.0.0.1:3000')):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Port occupied; refusing replacement')
        with (OUT/(name+'-formal.log')).open('xb') as log:
            process=subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        owned[name]=process_records('ProcessId='+str(process.pid))[0]
        OWNED.write_text(json.dumps(owned,indent=2)+'\n',encoding='utf-8')
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            try:
                if httpx.get(url,timeout=2,trust_env=False).status_code==200:break
            except httpx.HTTPError:pass
            if process.poll() is not None:raise RuntimeError('Service exited; inspect private log')
            time.sleep(.2)
        else:raise RuntimeError('Startup timeout')
        print(f'Started formal {name} port{port}, launcher PID{process.pid}')
    checks=[]
    with httpx.Client(base_url='http://127.0.0.1:3000',trust_env=False,timeout=10) as client:
        for method,path,expected,kwargs in (
            ('GET','/',200,{}),('GET','/api/health',200,{}),
            ('GET','/api/documents/unknown/parsing',401,{}),
            ('POST','/api/documents/unknown/parsing',403,{'json':{},'headers':{'Origin':'https://bad.invalid'}}),
            ('POST','/api/index',403,{'files':{'file':('probe.pdf',b'%PDF-probe','application/pdf')},'headers':{'Origin':'https://bad.invalid'}})):
            response=client.request(method,path,**kwargs)
            checks.append({'name':method+' '+path,'expected':expected,'actual':response.status_code,'passed':response.status_code==expected})
    if not all(c['passed'] for c in checks):raise AssertionError(checks)
    write(ROOT/'docs/checks/stage2-4-formal-http.json',{'round':'R20','overall':'passed','checks':checks,'credentials':'anonymous only'})


def restart_backend():
    owned=read(OWNED);saved=owned['backend']
    if process_records('ProcessId='+str(saved['ProcessId']))!=[saved]:
        raise RuntimeError('Backend identity changed; refusing restart')
    subprocess.run(['taskkill','/PID',str(saved['ProcessId']),'/T','/F'],check=True,capture_output=True)
    env={k:v for k,v in os.environ.items() if not k.startswith('LAYOUTPATCH_')}
    env.update(PYTHONUTF8='1',APP_ORIGIN='http://127.0.0.1:3000',SESSION_COOKIE_SECURE='false')
    with (OUT/'backend-formal-final.log').open('xb') as log:
        process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--workers','1','--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    owned['backend']=process_records('ProcessId='+str(process.pid))[0]
    OWNED.write_text(json.dumps(owned,indent=2)+'\n',encoding='utf-8')
    for _ in range(100):
        try:
            if httpx.get('http://127.0.0.1:8000/health',trust_env=False,timeout=1).status_code==200:
                print('Restarted identity-verified formal backend with final source, launcher PID'+str(process.pid));return
        except httpx.HTTPError:pass
        if process.poll() is not None:raise RuntimeError('Final backend failed to start')
        time.sleep(.2)
    raise RuntimeError('Final backend startup timed out')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('stop','migrate','start','restart-backend'));args=parser.parse_args()
    {'stop':stop_services,'migrate':migration,'start':start_services,'restart-backend':restart_backend}[args.action]()
