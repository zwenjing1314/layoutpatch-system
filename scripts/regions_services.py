"""R22 identity-guarded local service lifecycle; never touches Qdrant or formal auth."""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import time

import httpx
from backend.db.connection import ROOT
from scripts.check_stage1b_acceptance import process_records
from scripts.check_regions import OUT,ORIGIN,read
from scripts.check_regions_http import save

OWNED=OUT/'services.json'


def stop(record):
    if process_records('ProcessId='+str(record['ProcessId']))!=[record]:raise RuntimeError('Process identity changed; refusing stop')
    subprocess.run(['taskkill','/PID',str(record['ProcessId']),'/T','/F'],capture_output=True,check=True)


def launch(name,port,module=None):
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Port occupied')
    env={k:v for k,v in os.environ.items() if not k.startswith('LAYOUTPATCH_')}
    env.update(PYTHONUTF8='1',APP_ORIGIN=ORIGIN,SESSION_COOKIE_SECURE='false',NEXT_TELEMETRY_DISABLED='1')
    args=([sys.executable,'-B','-m','uvicorn',module,'--host','127.0.0.1','--port',str(port),'--workers','1','--no-access-log'] if module else [shutil.which('node'),'node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',str(port)])
    n=1
    while (OUT/f'{name}-{n}.log').exists():n+=1
    with (OUT/f'{name}-{n}.log').open('xb') as log:
        p=subprocess.Popen(args,cwd=ROOT if module else ROOT/'frontend',env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    record=process_records('ProcessId='+str(p.pid))[0]
    owned=read(OWNED) if OWNED.exists() else {};owned[name]=record;save(OWNED,owned)
    for _ in range(150):
        try:
            if httpx.get(f'http://127.0.0.1:{port}'+('/health' if module else ''),trust_env=False,timeout=1).status_code==200:
                print(name,'ready',port,'launcher',p.pid);return record
        except httpx.HTTPError:pass
        if p.poll() is not None:raise RuntimeError('Service exited; inspect private log')
        time.sleep(.2)
    raise TimeoutError('Service startup')


def main(action):
    if action=='stop-frontend':
        record=process_records('ProcessId=55840')
        if len(record)!=1 or record[0]['Created']!='2026-11-07T23:17:49.1013820Z' or 'node_modules/next/dist/bin/next start' not in record[0]['CommandLine']:raise RuntimeError('Formal frontend changed')
        save(OUT/'formal-frontend-before.json',record[0]);stop(record[0]);print('Stopped verified frontend before build')
    elif action=='switch-isolated':
        formal=process_records('ProcessId=47100');isolated=process_records('ProcessId=42236')
        if len(formal)!=1 or formal[0]['Created']!='2026-11-07T23:22:45.5500360Z' or '-m uvicorn backend.main:app' not in formal[0]['CommandLine']:raise RuntimeError('Formal backend changed')
        if len(isolated)!=1 or 'scripts.regions_acceptance_server:app' not in isolated[0]['CommandLine'] or '--port 8001' not in isolated[0]['CommandLine']:raise RuntimeError('Isolated backend changed')
        save(OUT/'formal-backend-before.json',formal[0]);save(OUT/'isolated8001-before.json',isolated[0])
        stop(isolated[0]);stop(formal[0]);launch('isolated',8000,'scripts.regions_acceptance_server:app');launch('frontend',3000)
    elif action=='restart-isolated':
        stop(read(OWNED)['isolated']);launch('isolated',8000,'scripts.regions_acceptance_server:app')
    elif action=='restore':
        owned=read(OWNED);stop(owned['isolated']);launch('formal',8000,'backend.main:app')
        print('Formal backend and new production frontend running; test backend/model stopped')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stop-frontend','switch-isolated','restart-isolated','restore']);main(p.parse_args().action)
