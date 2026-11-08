"""R21 final formal DB/index/source/feature/dependency protection, no credentials."""
import hashlib
import importlib.metadata as metadata
import json
import subprocess

import httpx

from backend.db.connection import ROOT,DEFAULT_DATABASE
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.check_selection_http import dynamic_fingerprint


def read(path):return json.loads(path.read_text('utf-8'))


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    base=read(ROOT/'docs/checks/stage2-5-preflight.json');checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value:raise AssertionError(name)
    check('formal_all_tables_revision_integrity_fk_unchanged',snapshot(DEFAULT_DATABASE)==base['database'])
    check('formal13_full_vectors_payload_config_unchanged',vector_fingerprint(base['collection'])==base['qdrant'])
    check('reused24_full_vectors_payload_config_unchanged',dynamic_fingerprint(base['reused_collection'],base['reused_count'])==base['reused_qdrant'])
    check('r19_database_unchanged',snapshot(ROOT/'runtime/verification/r19/ui/metadata.sqlite3')==base['r19_source'])
    check('r20_database_unchanged',snapshot(ROOT/'runtime/verification/r20/metadata.sqlite3')==base['r20_source'])
    check('all11_reused_full_bf16_and_exports_unchanged',all(digest(ROOT/p)==expected for p,expected in base['features'].items()))
    for name,expected in base['protected'].items():check('protected_'+name,digest(ROOT/name)==expected)
    for name,expected in base['resources'].items():check('resource_'+name,digest(ROOT.parent/name)==expected)
    for relative,repos in base['sources'].items():
        for repo,expected in repos.items():check('source_'+repo+'/'+relative,digest(ROOT.parent/repo/'src/layoutpatch'/relative)==expected)
    before=read(ROOT/'docs/checks/source-state-r21-before.json');after=read(ROOT/'docs/checks/source-state-r21-final.json')
    for repo in ('layoutpatch','layoutpatch-evidence','Snappy'):check(repo+'_git_boundary_unchanged',before[repo]==after[repo])
    check('frozen_model_environment_unchanged',before['model_environment']==after['model_environment'])
    check('web_dependencies_unchanged',sorted([d.metadata['Name'],d.version] for d in metadata.distributions())==base['web_packages'])
    check('no_2_6_public_region_endpoint',not any('/regions' in p for p in read(ROOT/'frontend/docs/openapi.json')['paths']))
    profile=read(ROOT/'configs/d_no_text_local.json')
    check('final_d_code_identity',all(digest(ROOT/p)==expected for p,expected in profile['code_sha256'].items()))
    check('local_checkpoint_copy_matches_frozen',digest(ROOT/profile['checkpoint'])==profile['checkpoint_sha256'])
    with httpx.Client(base_url='http://127.0.0.1:3000',trust_env=False,timeout=10) as client:
        for path,code in (('/',200),('/api/health',200),('/api/documents',401),('/api/documents/unknown/parsing',401)):
            response=client.get(path);check('formal_anonymous_'+path,response.status_code==code)
            if path.startswith('/api/') and path!='/api/health':
                check('formal_no_store_'+path,response.headers.get('cache-control')=='private, no-store')
        response=client.post('/api/index',files={'file':('probe.pdf',b'%PDF-probe','application/pdf')},headers={'Origin':'https://bad.invalid'})
        check('formal_upload_origin403',response.status_code==403)
    ps='Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -In 3000,8000,8001,6333 | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress'
    ports=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True))
    check('ports_formal_present_test_absent',{p['LocalPort'] for p in ports}=={3000,8000,6333})
    ps="Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | ConvertTo-Json -Compress"
    processes=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True))
    check('test_model_parser_workers_stopped',not any('model_query_worker.py' in (p['CommandLine'] or '') or 'mineru_page_worker.py' in (p['CommandLine'] or '') for p in processes))
    files=list((ROOT/'runtime/regions/d-no-text').glob('*/*'))
    report={'round':'R21','overall':'passed','checks':checks,'ports':ports,'processes':processes,
        'derived_cache':{'pages':len([p for p in files if p.name=='patches.pt']),'bytes_with_manifests':sum(p.stat().st_size for p in files if p.is_file()),
            'path':'runtime/regions/d-no-text','format':'CPU float32 [1024,128], immutable content-addressed folders, original BF16 and Qdrant retained'},
        'scope':'Fresh R21-before/final comparisons. Old repos checked by Git/selected source/resource/environment scope, not ignored whole disk. Formal services retained without restart, credentials unused. Anonymous localhost requests only.'}
    with (ROOT/'docs/checks/stage2-5-protection.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'checks':len(checks),'passed':True,'derived_cache':report['derived_cache'],'ports':ports}))


if __name__=='__main__':main()
