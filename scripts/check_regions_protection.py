"""R22 fresh final comparisons and formal anonymous HTTP only."""
import hashlib
import importlib.metadata as metadata
import json
import subprocess
import httpx
from backend.db.connection import ROOT,DEFAULT_DATABASE
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.check_selection_http import dynamic_fingerprint
from scripts.check_regions_http import save


def read(path):return json.loads(path.read_text('utf-8'))
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    baseline=read(ROOT/'docs/checks/stage2-6-preflight.json');checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value:raise AssertionError(name)
    check('formal0008_all_tables_schema_integrity_fk_unchanged',snapshot(DEFAULT_DATABASE)==baseline['database'])
    check('formal13_complete_vectors_payload_config_unchanged',vector_fingerprint(baseline['collection'])==baseline['qdrant'])
    check('reused24_complete_vectors_payload_config_unchanged',dynamic_fingerprint(baseline['reused_collection'],baseline['reused_count'])==baseline['reused_qdrant'])
    for path,value in baseline['source_databases'].items():check('source_database_'+path,snapshot(ROOT/path)==value)
    for path,value in baseline['protected'].items():check('protected_'+path,digest(ROOT/path)==value)
    for path,value in baseline['features'].items():check('reused_feature_'+path,digest(ROOT/path)==value)
    for path,value in baseline['old_resources'].items():check('old_resource_'+path,digest(ROOT.parent/path)==value)
    before=read(ROOT/'docs/checks/source-state-r22-before.json');after=read(ROOT/'docs/checks/source-state-r22-final.json')
    for name in ('layoutpatch','layoutpatch-evidence','Snappy','model_environment'):check(name+'_boundary_unchanged',before[name]==after[name])
    check('web_dependencies_unchanged',sorted([d.metadata['Name'],d.version] for d in metadata.distributions())==baseline['web_dependencies'])
    profile=read(ROOT/'configs/d_no_text_local.json')
    check('frozen_D_algorithm_code_identity',all(digest(ROOT/p)==expected for p,expected in profile['code_sha256'].items()))
    with httpx.Client(base_url='http://127.0.0.1:3000',trust_env=False,timeout=15) as c:
        for path,expected in [('/',200),('/api/health',200),('/api/documents',401),('/api/pages/unknown/regions/status',401),('/api/pages/unknown/regions/1/crop',401)]:
            r=c.get(path);check('formal_anonymous_'+path,r.status_code==expected)
            if expected==401:check('formal_no_store_'+path,r.headers.get('cache-control')=='private, no-store')
        payload={'q':'anonymous protection probe','document_version_id':'00000000-0000-4000-8000-000000000000','render_sha256':'a'*64,'index_generation':'00000000-0000-4000-8000-000000000000'}
        r=c.post('/api/pages/unknown/regions',json=payload,headers={'Origin':'http://127.0.0.1:3000'})
        check('formal_anonymous_region_POST401',r.status_code==401)
        r=c.post('/api/index',files={'file':('probe.pdf',b'%PDF-probe','application/pdf')},headers={'Origin':'https://bad.invalid'})
        check('formal_upload_Origin403_retained',r.status_code==403)
        r=c.post('/api/pages/unknown/regions',json={},headers={'Origin':'https://bad.invalid'})
        check('formal_region_Origin403',r.status_code==403)
    ps='Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -In 3000,8000,8001,6333 | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress'
    ports=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True))
    check('formal_ports_present_test8001_absent',{p['LocalPort'] for p in ports}=={3000,8000,6333})
    ps="Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | ConvertTo-Json -Compress"
    processes=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True))
    check('test_model_parser_server_stopped',not any(any(name in (p['CommandLine'] or '') for name in ('model_query_worker.py','mineru_page_worker.py','scripts.regions_acceptance_server:app')) for p in processes))
    # Recheck auth tables after anonymous requests as well.
    check('formal_all_tables_unchanged_after_anonymous_checks',snapshot(DEFAULT_DATABASE)==baseline['database'])
    report={'round':'R22','overall':'passed','checks':checks,'ports':ports,'processes':processes,'limits':'Formal credentials unused. Old repositories protected by Git/selected resource/environment hashes, not an ignored whole-disk audit. Only project service trees restarted; Docker/Qdrant retained.'}
    save(ROOT/'docs/checks/stage2-6-protection.json',report);print('Protection passed',len(checks),'checks; formal login not used')


if __name__=='__main__':main()
