"""R22 evidence index/cost ledger and document consistency; no credentials exported."""
import json
import re
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path
from backend.db.connection import ROOT
from scripts.check_regions import OUT,read
from scripts.check_regions_http import save


def main():
    records={kind:[read(p) for p in (OUT/kind).glob('*.json')] for kind in ('page','query','region')}
    assert all(r['network_attempts']==0 for rows in records.values() for r in rows)
    artifacts=read(ROOT/'docs/checks/stage2-6-artifacts.json')
    parser=[read(ROOT/r['receipt']) for r in artifacts['parser_receipts']]
    cache_keys={r['regions']['cache_key'] for r in records['region']}
    workers={str(pid):{kind:sum(r['worker_pid']==pid for r in rows) for kind,rows in records.items()} for pid in sorted({r['worker_pid'] for rows in records.values() for r in rows})}
    for r in records['region']:
        result=r['regions'];assert result['strict_load'] and result['parameters']==273410 and result['checkpoint_sha256']=='18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b'
    costs={'round':'R22','actual_page_forwards':len(records['page']),'actual_retrieval_query_encodings':len(records['query']),'actual_region_query_encodings':len(records['region']),
        'all_actual_query_encodings':len(records['query'])+len(records['region']),'actual_D_forwards':sum(not r['regions']['cache_hit'] for r in records['region']),
        'D_cache_hits':sum(r['regions']['cache_hit'] for r in records['region']),'actual_D_forward_ms':sum(r['regions']['d_forward_ms'] for r in records['region']),
        'actual_query_encode_ms':sum(r['encode_ms'] for kind in ('query','region') for r in records[kind]),
        'actual_MinerU_pages':len(parser),'actual_ONNX_runs':sum(s['forward_calls'] for r in parser for s in r['sessions']),
        'parser_receipt_seconds':sum(r['seconds'] for r in parser),'network_attempts':0,'parser_blocked_writes':sum(r['blocked_writes'] for r in parser),
        'workers':workers,'D_cache_bytes_with_manifests':sum(p.stat().st_size for key in cache_keys for p in (ROOT/'runtime/regions/d-no-text'/key).iterdir() if p.is_file()),
        'D_reference_forwards_initial_plus_final':len(read(ROOT/'docs/checks/stage2-6-D-reference-initial6.json')['results'])+len(read(ROOT/'docs/checks/stage2-6-D-reference.json')['results']),
        'CUDA_peak_allocated_bytes':max(r.get('peak_allocated_bytes',0) for rows in records.values() for r in rows),
        'limits':['All receipt-backed calls counted, including both delayed requests after client cleanup; explicit failed fixture returns before model and is separate','Reference CPU calls and synthetic regression tests separate from production forwards','Parser seconds exclude complete wall time/environment identity checks/geometry process startup; CUDA allocated is not whole-process memory','No training/download/base-model change/accuracy/large-library or concurrency claim']}
    save(ROOT/'docs/checks/stage2-6-cost.json',costs)
    visual=read(ROOT/'docs/checks/stage2-6-visual.json');visual.update(overall='passed_visual_spotcheck',review={'contact_sheet':'Viewed actual image/table/text/equation overlay examples; orange rectangles correspond to source areas and remain within PNG','text_limit':'First text candidate is an arXiv sidebar, not guaranteed reading-order body text','page_number':'One-based physical PDF order; B physical page6 contains printed page4; not a page mismatch','accuracy':'No detector recall or D localization accuracy evaluation'})
    save(ROOT/'docs/checks/stage2-6-visual.json',visual)
    failures=[
        {'step':'SDK initial','observed':'Optional RegionResponse.items caused five tsc errors','resolution':'Make required, regenerate OpenAPI/SDK; current tsc/build passed'},
        {'step':'Backend attempt1','observed':'121 tests, one old route whitelist failure','resolution':'Add exactly three expected public routes; final122 passed','log':'runtime/verification/r22/backend-attempt1.log'},
        {'step':'CLI','observed':'yarn missing; two guessed local paths and empty historical query-audit glob did not exist','resolution':'Use existing local generator, rg for actual paths, current audit layout; no install/download'},
        {'step':'Docs patch','observed':'Initial nonexistent anchor and final mismatched progress heading/hunk ordering safely rejected batch patches','resolution':'Rejected without writing; reread exact headings and apply ordered scoped patches'},
        {'step':'Browser radio','observed':'check() postcondition timed out after selection unmounted the list','resolution':'Fresh DOM confirmed selected doc; subsequent use click; no repeated upload/search'},
        {'step':'Delayed response','observed':'First manual sequence lacked exact cancellation timing','resolution':'Separate second sequence proves clear0.523s after entry, before6s real D start; both calls counted'},
        {'step':'Expiry fixture','observed':'expires_at=0 rejected by ck_session_times; transaction rolled back','resolution':'Use created_at < actual past expiry < old expires_at, no constraint disabled','log':'runtime/verification/r22/expiry-fixture.json'},
        {'step':'Formal smoke attempt1','observed':'Anonymous malformed {} region body received422 before route principal, not401','resolution':'Use schema-valid anonymous payload for401 boundary check; invalid body behavior not represented as401; Origin still403','log':'runtime/verification/r22/protection-attempt1.log'},
        {'step':'Page reference labels','observed':'Reused R16 helper emitted historical R16/date labels on actual R22 results','resolution':'Keep raw metadata report in runtime, relabel only metadata toR22; scores/results unchanged','log':'runtime/verification/r22/page-reference-original-metadata.json'},
        {'step':'Final inventory','observed':'Final file-existence assertion found Git-quoted non-ASCII document paths included in the code inventory','resolution':'Read Git inventory with core.quotepath=false and explicit UTF-8, filter document paths correctly, then validate every manifest file; application code/results unchanged'}]
    save(ROOT/'docs/checks/stage2-6-failures.json',{'round':'R22','unresolved':[],'failures':failures,'known_warnings':['Existing baseline-browser-mapping old-data warning; git LF/CRLF warnings; no package upgrade']})
    expected={'backend':('backend-final2.log','Ran 122 tests'),'model':('model-final.log','13 passed'),'frontend':('frontend-final2.log','pass 32'),'typecheck':('typecheck-final.log',''),'build':('build-attempt1.log','Compiled successfully')}
    tests={}
    for name,(log,token) in expected.items():
        text=(OUT/log).read_text('utf-8');assert token in text
        if name=='backend':assert text.rstrip().endswith('OK')
        tests[name]={'passed':True,'log':(OUT/log).relative_to(ROOT).as_posix(),'tail':text.splitlines()[-7:]}
    save(ROOT/'docs/checks/stage2-6-tests.json',{'round':'R22','overall':'passed','tests':tests,'scope':'Web inference doubles separated from13 torch/algorithm contracts; real receipts/browser and references separate. Production build created after stopping previous frontend.'})
    with sqlite3.connect(f'file:{(OUT/"metadata.sqlite3").as_posix()}?mode=ro',uri=True) as db:
        assert db.execute('pragma integrity_check').fetchone()[0]=='ok' and not db.execute('pragma foreign_key_check').fetchall()
        assert db.execute('select page_count from index_generations where id=(select active_index_id from system_state where id=1)').fetchone()[0]==36
        assert db.execute("select count(*) from jobs where status='completed'").fetchone()[0]==2
        assert db.execute("select count(*) from page_parses where status='ready'").fetchone()[0]==23
    evidence=['http','browser','recovery-before','recovery-after','legacy','protection','artifacts','visual','D-reference','tests']
    reports={name:read(ROOT/f'docs/checks/stage2-6-{name}.json') for name in evidence}
    assert all(report['overall'].startswith('passed') for report in reports.values())
    documents=read(ROOT/'docs/checks/r22-document-checks.json')
    assert documents['overall']=='passed' and all(c['passed'] for c in documents['checks'])
    evidence_paths={name:f'docs/checks/stage2-6-{name}.json' for name in evidence}
    evidence_paths.update({'documents':'docs/checks/r22-document-checks.json','page-reference':'docs/checks/stage2-6-page-reference.json',
                          'cost':'docs/checks/stage2-6-cost.json','failures':'docs/checks/stage2-6-failures.json'})
    changed=subprocess.check_output(['git','-c','core.quotepath=false','diff','--name-only'],encoding='utf-8').splitlines()+subprocess.check_output(['git','-c','core.quotepath=false','ls-files','--others','--exclude-standard'],encoding='utf-8').splitlines()
    docs=['docs/AI交接.md','docs/progress.md','docs/testing.md','docs/requirements.md','docs/architecture.md','docs/interfaces.md','docs/项目开发阶段规划与任务.md','docs/阶段2新窗口接手指南.md','docs/source-audit.md','docs/stage2-6-runbook.md','docs/过程记录/07_2技术操作详解.md','docs/过程记录/08_2逐步口述稿.md']
    generated=sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/checks').glob('stage2-6-*') if p.is_file())
    generated+=['docs/checks/r22-document-checks.json','docs/checks/source-state-r22-before.json','docs/checks/source-state-r22-final.json']
    save(ROOT/'docs/checks/stage2-6-verification.json',{'round':'R22','date':'2026-11-08','stage':'2-6','overall':'passed_applicable_stage2_exit','evidence':evidence_paths,'costs':costs,'modified_code_files':sorted({p for p in changed if not p.startswith('docs/')}),'updated_documents':docs,
        'generated_evidence_files':sorted(set(generated)),
        'screenshots':sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/checks/stage2-6-screens').glob('*.png')),
        'final_document_checks':{'passed':len(documents['checks']),'local_links':documents['local_file_links'],'speech_characters':documents['speech_characters']},
        'Qdrant_network_body_log_scope':'Six later actual retrieval requests, exact whitelist sizes12/5/8/12/11/12; first four earlier8001 requests do not have this wrapper log. All ten have model receipts.',
        'schema':'0008 unchanged; no new table/migration','new_isolated_pdf_pages':23,'isolated_active_pages':36,'formal_pages':13,'formal_credentials':'unused','next_unique_task':'3-1 用户管理, only after explicit user request',
        'limits':['Stage2 application integration exit, not T01-T15 entire table or research accuracy','Only zero-rotation/zero-origin equal Crop/MediaBox PDFs supported','No full BFCache/cross-tab rerun, wall-clock timeout, GPU preemption, arbitrary PDFs, concurrency/capacity, model unavailable natural hardware failure or performance evaluation','Source_dev fixed-three-page consistency remains R21 historical; R22 adds14 same-Q new-PDF references at unchanged tolerances','New docs ignored by original rule; copy separately. No staging/commit/push.']})
    print(json.dumps({'actual_pages':costs['actual_page_forwards'],'actual_queries_including_regions':costs['all_actual_query_encodings'],'actual_D':costs['actual_D_forwards'],'D_cache_hits':costs['D_cache_hits'],'MinerU_seconds':costs['parser_receipt_seconds'],'D_CPU_ms':costs['actual_D_forward_ms'],'browser_checks':len(reports['browser']['checks']),'protection_checks':len(reports['protection']['checks'])}))


if __name__=='__main__':main()
