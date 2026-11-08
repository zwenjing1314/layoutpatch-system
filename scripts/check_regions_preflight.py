"""R22 fresh baseline and online backup; no credential values exported."""
from contextlib import closing
import hashlib
import importlib.metadata as metadata
import json
import sqlite3
import subprocess
from backend.db.connection import ROOT,DEFAULT_DATABASE
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.check_selection_http import dynamic_fingerprint

OUT=ROOT/'runtime/verification/r22'


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    with closing(sqlite3.connect(DEFAULT_DATABASE)) as src,closing(sqlite3.connect(OUT/'metadata-before.sqlite3')) as dst:
        src.backup(dst)
        collection=src.execute('SELECT collection_name FROM index_generations WHERE id=(SELECT active_index_id FROM system_state WHERE id=1)').fetchone()[0]
    reused=ROOT/'runtime/verification/r19/ui/metadata.sqlite3'
    with closing(sqlite3.connect(f'file:{reused.as_posix()}?mode=ro',uri=True)) as db:
        rc,count=db.execute('SELECT collection_name,page_count FROM index_generations WHERE id=(SELECT active_index_id FROM system_state WHERE id=1)').fetchone()
        features=[ROOT/p for row in db.execute('SELECT tensor_path,export_path FROM page_features') for p in row]
    paths=[ROOT/'.gitignore',*ROOT.glob('requirements-*'),ROOT/'configs/colpali_local.json',ROOT/'configs/d_no_text_local.json',ROOT/'frontend/package.json',ROOT/'frontend/yarn.lock',
        *sorted((ROOT/'docs/过程记录').glob('0[1-6]*')),*sorted((ROOT/'backend/algorithms').rglob('*.py')),
        ROOT/'runtime/models/d-no-text/seed_0_epoch_01.pt']
    source=ROOT/'docs/checks/stage2-5-preflight.json'
    previous=json.loads(source.read_text('utf-8'))
    resources={name:digest(ROOT.parent/name) for name in previous['resources']}
    for name,value in resources.items():assert value==previous['resources'][name]
    processes=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',"Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='node.exe'\" | Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | ConvertTo-Json -Compress"],text=True))
    ports=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -In 3000,8000,8001,6333 | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress'],text=True))
    source_dbs=['runtime/verification/r19/ui/metadata.sqlite3','runtime/verification/r20/metadata.sqlite3','runtime/verification/r21/metadata.sqlite3']
    report={'round':'R22','date':'2026-11-08','stage':'2-6','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'status_after_preflight_helper_creation':subprocess.check_output(['git','status','--short'],text=True),'initial_status':'clean observed before creating this helper',
        'database':snapshot(DEFAULT_DATABASE),'collection':collection,'qdrant':vector_fingerprint(collection),
        'reused_collection':rc,'reused_count':count,'reused_qdrant':dynamic_fingerprint(rc,count),
        'source_databases':{p:snapshot(ROOT/p) for p in source_dbs},'protected':{p.relative_to(ROOT).as_posix():digest(p) for p in paths if p.is_file()},
        'features':{p.relative_to(ROOT).as_posix():digest(p) for p in features},'old_resources':resources,
        'web_dependencies':sorted((d.metadata['Name'],d.version) for d in metadata.distributions()),'ports':ports,'processes':processes,
        'visible_other_project_chats':'two same-project other chats notLoaded; no active same-scope edits observed'}
    with (ROOT/'docs/checks/stage2-6-preflight.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'revision':report['database']['revision'],'documents':report['database']['tables']['documents']['count'],'pages':report['database']['tables']['pages']['count'],'ports':ports}))


if __name__=='__main__':main()
