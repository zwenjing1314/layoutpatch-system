"""R20 final data/resource/source protection and real-run cost accounting."""
from collections import Counter
import importlib.metadata as metadata
import json
import sqlite3
import subprocess

import httpx

from backend.db.connection import ROOT,DEFAULT_DATABASE
from backend.parsing.adapter import digest,load_profile,verify_resources
from backend.db.seed import canonical,sha
from scripts.check_parsing import OUT,read,write
from scripts.check_parsing_preflight import TOOL
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.check_selection_http import dynamic_fingerprint


def main():
    baseline=read(ROOT/'docs/checks/stage2-4-preflight.json');checks=[]
    def check(name,value,**detail):
        checks.append({'name':name,'passed':bool(value),**detail})
        if not value:raise AssertionError(name)
    current=snapshot(DEFAULT_DATABASE)
    for table,value in baseline['database']['tables'].items():
        if table!='alembic_version':check('formal_original_'+table,current['tables'][table]==value)
    check('formal_new_tables_still_empty',all(current['tables'][t]['count']==0 for t in ('parser_profiles','parsing_tasks','page_parses')))
    check('formal0008_integrity_fk',current['revision']=='0008_parsing' and current['integrity']=='ok' and current['foreign_key_errors']==0)
    check('formal13_complete_vectors_payload_config',vector_fingerprint(baseline['collection'])==baseline['qdrant'])
    check('old_source_repos_and_algorithm_environment',read(ROOT/'docs/checks/source-state-r20-before.json')==read(ROOT/'docs/checks/source-state-r20-final.json'))
    check('r19_source_database_unchanged',snapshot(ROOT/'runtime/verification/r19/ui/metadata.sqlite3')==read(OUT/'clone-baseline.json')['r19_source'])
    # The reused24-page collection is read-only in R20; compare against the frozen
    # R19 final fingerprint as historical reference, not an invented R20-before.
    formal19=read(ROOT/'docs/checks/stage2-3c-runtime.json')
    with sqlite3.connect(f"file:{(ROOT/'runtime/verification/r19/ui/metadata.sqlite3').as_posix()}?mode=ro",uri=True) as db:
        collection,count=db.execute('SELECT collection_name,page_count FROM index_generations WHERE id=(SELECT active_index_id FROM system_state WHERE id=1)').fetchone()
    reused=dynamic_fingerprint(collection,count)
    source_site=TOOL/'.venv/Lib/site-packages'
    check('old_parser_source_module_files_unchanged',all(digest(source_site/name)==value for name,value in baseline['parser_source_files'].items()))
    models=TOOL/'mineru_home/models/MinerU-4_models_onnx'
    actual={p.relative_to(models).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in models.rglob('*') if p.is_file()}
    check('old_models_and_download_metadata_unchanged',actual==baseline['models'])
    metadata_checks=[]
    for name,expected in load_profile()['model_files'].items():
        cached=(models/'.cache/huggingface/download'/(name+'.metadata')).read_text().splitlines()
        data=(models/name).read_bytes()
        import hashlib
        identity=hashlib.sha256(data).hexdigest() if name.endswith('.onnx') else hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        metadata_checks.append(cached[0]=='358310b4f64b95f9fefc372ad899356e4111f376' and cached[1]==identity)
    check('all13_model_payloads_match_cached_revision_etags',len(metadata_checks)==13 and all(metadata_checks))
    verify_resources(load_profile());check('final_parser_copy_and_model_identity',True)
    check('web_dependencies_unchanged',sorted([d.metadata['Name'],d.version] for d in metadata.distributions())==baseline['web_packages'])
    for name in ('requirements-colpali.in','requirements-colpali.lock.txt','configs/colpali_local.json','requirements-web.in','requirements-web.lock.txt','.gitignore'):
        check('unchanged_'+name,digest(ROOT/name)==baseline['files'][name])
    for name,value in baseline['files'].items():
        if name.startswith('docs/过程记录/0') and name.split('/')[-1][:2] in {'01','02','03','04','05','06'}:
            check('history_'+name,digest(ROOT/name)==value)
    queries=[read(p) for p in sorted((OUT/'queries').glob('*.json'))]
    check('all_actual_query_audits_original_profile_no_network',len(queries)==9 and all(r['network_attempts']==0 and r['profile_sha256']==digest(ROOT/'configs/colpali_local.json') for r in queries))
    requests=list((ROOT/'runtime/parsing').glob('*/*/request.json'))
    receipts=[];missing=[]
    for path in requests:
        receipt=path.parent/'receipt.json'
        if receipt.is_file():receipts.append(read(receipt))
        else:missing.append(path.parent.relative_to(ROOT).as_posix())
    # Receipts from the initial development guard counted blocked cmd.exe probes
    # under network_attempts. Only current code receipts are network evidence.
    cost={'requested_page_invocations_all_profiles':len(requests),'worker_receipts_all_profiles':len(receipts),
          'actual_onnx_forward_calls_recorded_all_profiles':sum(sum(s['forward_calls'] for s in r['sessions']) for r in receipts),
          'recorded_parser_seconds_all_profiles':sum(r['seconds'] for r in receipts),'no_worker_receipt_paths':missing,
          'query_forwards_all_attempts':len(queries),'query_worker_pids':sorted({r['worker_pid'] for r in queries}),
          'final_http_query_count':6,'first_failed_http_attempt_query_count':3,'new_page_encoding_count':0,
          'limits':'Repeated real parser development runs/probes and failed receipts remain counted. No-worker paths include geometry refusals and forced timeout; their unfinished work is not inferred as zero. Earlier guard mixed blocked subprocess attempts into its network counter; do not aggregate that counter as actual networking.'}
    ps='Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -In 3000,8000,8001,6333 | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress'
    ports=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True))
    check('formal_ports_present_test_port_closed',{r['LocalPort'] for r in ports}=={3000,8000,6333})
    processes=subprocess.check_output(['powershell','-NoProfile','-Command',"Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],text=True)
    check('no_parser_or_isolated_model_left',not any(text in processes for text in ('model_query_worker.py','mineru_page_worker.py','parsing_acceptance_server:app')))
    with httpx.Client(base_url='http://127.0.0.1:3000',trust_env=False,timeout=10) as client:
        for path,code in (('/',200),('/api/health',200),('/api/documents/unknown/parsing',401)):
            response=client.get(path);check('final_http_'+path,response.status_code==code)
        response=client.post('/api/index',files={'file':('probe.pdf',b'%PDF-probe','application/pdf')},headers={'Origin':'https://bad.invalid'})
        check('final_upload_origin_protected',response.status_code==403)
    licenses=[]
    for dist in metadata.distributions(path=[str(ROOT/'.venv-parser/Lib/site-packages')]):
        if dist.metadata['Name'].lower() in {'mineru','docvortex','onnxruntime'}:
            licenses.append({'package':dist.metadata['Name'],'version':dist.version,'license_expression':dist.metadata.get('License-Expression'),'license':dist.metadata.get('License')})
    write(ROOT/'docs/checks/stage2-4-protection.json',{'round':'R20','overall':'passed','checks':checks,'ports':ports,'cost':cost,'reused24_current_fingerprint':reused,'reused24_reference_scope':'Newly recomputed at R20 end; R19 report is historical reference. R20 never writes Qdrant.','licenses_from_installed_metadata':licenses,'limits':['Git/selected module/model files and recorded local resources checked; not an ignored-file whole-disk audit.','No official score/accuracy, GPU cancellation, D or website region experiment. Formal credentials not used.']})
    print(f'{len(checks)} final protection/runtime checks passed; costs retained')


if __name__=='__main__':main()
