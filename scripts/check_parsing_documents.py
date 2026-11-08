"""Finalize R20 report and verify append-only learning/history and exact changed-file scope."""
import ast
import json
import re
import subprocess
from pathlib import Path

from backend.db.connection import ROOT,DEFAULT_DATABASE
from backend.parsing.adapter import digest
from scripts.check_parsing import OUT,read,write
from scripts.check_stage2_preflight import snapshot

DOC_NAMES=('AI交接.md','progress.md','testing.md','requirements.md','architecture.md','interfaces.md','阶段2新窗口接手指南.md','项目开发阶段规划与任务.md','source-audit.md','过程记录/07_2技术操作详解.md','过程记录/08_2逐步口述稿.md','stage2-4-runbook.md')


def main():
    checks_dir=ROOT/'docs/checks';summary_path=checks_dir/'stage2-4-verification.json';doc_path=checks_dir/'r20-document-checks.json'
    write(checks_dir/'stage2-4-failures.json',{'round':'R20','unresolved':[],'records':[
        {'issue':'Windows source package path268 chars could not be read with normal path','evidence':'First seed traceback returned in tool output; no standalone first-attempt log saved. Normal_exists=false/extended_exists=true was actually checked.','resolution':'Extended Windows path for source reads/copy;112 distributions/17208 files verified','final_log':'runtime/verification/r20/parser-seed-attempt2.log'},
        {'issue':'Strict write guard initially counted Windows NUL output sink as3 forbidden writes','evidence':'runtime/verification/r20/parser-probe1.log','resolution':'Only exact resolved Windows NUL allowed; no other outside-attempt path permitted'},
        {'issue':'Initial combined guard counted3 blocked cmd.exe platform probes as network attempts','evidence':'runtime/verification/r20/parser-probe2.log and earlier failed receipts','resolution':'Separate process/network counters; extra processes remain denied; current11 network0/write escape0. Do not aggregate old counter as actual networking.'},
        {'issue':'Changing implementation while a development task existed invalidated frozen profile','evidence':'runtime/verification/r20/real-B-final.log','resolution':'PARSER_PROFILE_CHANGED correctly rejected; new profiles/attempt outputs created and final full11 pages rerun, no old output overwritten'},
        {'issue':'Real blank Page JSON omits blocks when default empty; exporter initially rejected','evidence':'runtime/verification/r20/faults-attempt1.log and raw output/schema.py default_factory=list','resolution':'Absent blocks accepted as default empty, explicit null invalid; actual longitudinal/landscape blank MinerU outputs now no_candidates'},
        {'issue':'Web unittest discover included pytest-only algorithm module, but Web env intentionally has no pytest','evidence':'runtime/verification/r20/backend-attempt1.log','resolution':'Explicit9 unittest modules under Web,4 algorithm CPU tests in frozen model .venv; no Web dependency install','final_log':'runtime/verification/r20/backend-final3.log'},
        {'issue':'HTTP acceptance logout omitted JSON media and original boundary rejected it','evidence':'runtime/verification/r20/http-final.log','resolution':'Test sends JSON{}; application security unchanged. First3 actual queries still counted,6 in final pass','final_log':'runtime/verification/r20/http-final2.log'},
        {'issue':'Fault clone copied one running source task while real parsing continued','evidence':'runtime/verification/r20/faults-clone-recovery.json','resolution':'Recovered only copied test metadata to interrupted; source/formal unchanged; future helper recovers clone at startup'},
        {'issue':'Existing baseline-browser-mapping/util._extend and Git newline notices','evidence':'runtime/verification/r20/build.log; frontend-formal.log; git diff --check','resolution':'Checks pass; no dependency/ignore upgrade'},
    ]})
    write(summary_path,{'round':'R20','overall':'building'});write(doc_path,{'round':'R20','overall':'building'})
    checks=[]
    def check(name,condition,**detail):
        checks.append({'name':name,'passed':bool(condition),**detail})
        if not condition:
            doc_path.write_text(json.dumps({'round':'R20','overall':'failed','checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
            raise AssertionError(name)
    for report,count in (('output',61),('faults',15),('http',46),('migration',19),('formal-http',5),('protection',42)):
        data=read(checks_dir/f'stage2-4-{report}.json')
        check(report+'_complete_pass',data['overall']=='passed' and len(data['checks'])==count and all(item['passed'] for item in data['checks']))
    check('visual_and_full_features_pass',read(checks_dir/'stage2-4-visual.json')['overall']=='passed' and read(checks_dir/'stage2-4-features.json')['checked_count']==24)
    log=(OUT/'backend-final3.log').read_text(encoding='utf-8')
    check('104_backend_tests_pass','Ran 104 tests' in log and log.rstrip().endswith('OK') and 'FAILED' not in log)
    check('25_frontend_tests_pass','pass 25' in (OUT/'frontend-tests.log').read_text(encoding='utf-8'))
    check('4_frozen_algorithm_cpu_tests_pass','4 passed' in (OUT/'colpali-cpu.log').read_text(encoding='utf-8'))
    check('typecheck_and_production_build',(OUT/'typecheck.log').stat().st_size==0 and 'Compiled successfully' in (OUT/'build.log').read_text(encoding='utf-8') and 'Route (app)' in (OUT/'build.log').read_text(encoding='utf-8'))
    baseline=read(checks_dir/'stage2-4-preflight.json')
    edited_allowed={'backend/main.py','backend/db/models.py','backend/db/seed.py','tests/test_auth.py','scripts/check_parsing_preflight.py','frontend/lib/api/generated/index.ts','frontend/lib/api/generated/services/DocumentsService.ts'}|{'docs/'+name for name in DOC_NAMES}
    edited=[name for name,value in baseline['files'].items() if (ROOT/name).is_file() and digest(ROOT/name)!=value]
    check('only_expected_existing_files_edited',set(edited)<=edited_allowed,files=edited)
    receipt=read(OUT/'document-update-receipt.json')
    for name in ('过程记录/07_2技术操作详解.md','过程记录/08_2逐步口述稿.md'):
        value=receipt[name];path=ROOT/'docs'/name
        import hashlib
        check('append_only_'+name,value['prefix_preserved'] and hashlib.sha256(path.read_bytes()[:value['old_bytes']]).hexdigest()==value['old_sha256']==baseline['files']['docs/'+name])
        text=path.read_text(encoding='utf-8')
        check('six_paired_steps_'+name,all(text.count(f'## 2026-11-08｜R20｜2-4｜S{i:02}：')==1 for i in range(1,7)))
    check('mouth60_to100',len(receipt['mouth_lengths'])==6 and all(60<=n<=100 for n in receipt['mouth_lengths']),lengths=receipt['mouth_lengths'])
    for name,value in baseline['files'].items():
        if name.startswith('docs/过程记录/0') and name.split('/')[-1][:2] in {'01','02','03','04','05','06'}:
            check('history_unchanged_'+name,digest(ROOT/name)==value)
    check('gitignore_and_dependency_locks_preserved',all(digest(ROOT/name)==baseline['files'][name] for name in ('.gitignore','requirements-colpali.in','requirements-colpali.lock.txt','requirements-web.in','requirements-web.lock.txt','frontend/package.json','frontend/yarn.lock')))
    missing=[]
    for name in DOC_NAMES:
        path=ROOT/'docs'/name;text=path.read_text(encoding='utf-8')
        for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',text):
            if target.startswith(('http:','https:','#')):continue
            target=target.split('#')[0]
            # Check newly added references only, not rewriting old historical links.
            if ('stage2-4' in target or 'r20-' in target) and not (path.parent/target).is_file():missing.append((name,target))
    check('new_local_doc_links_resolve',not missing,missing=missing)
    routes=json.loads((ROOT/'frontend/docs/openapi.json').read_text(encoding='utf-8'))['paths']
    check('SDK_openapi_two_protected_parse_operations',set(routes['/documents/{document_id}/parsing'])=={'get','post'} and 'getDocumentParsing' in (ROOT/'frontend/lib/api/generated/services/DocumentsService.ts').read_text() and 'requestDocumentParsing' in (ROOT/'frontend/lib/api/generated/services/DocumentsService.ts').read_text())
    check('no_region_rank_route_or_fake_ready_search_status',not any('regions' in route for route in routes) and 'Literal["not_requested"]' in (ROOT/'backend/search/routes.py').read_text())
    check('no_source_algorithm_or_pipeline_edits',all(digest(ROOT/name)==value for name,value in baseline['files'].items() if name.startswith('backend/algorithms/') or name in ('backend/documents/pipeline.py','backend/documents/uploads.py','frontend/app/page.tsx')))
    status=subprocess.check_output(['git','-c','core.quotepath=false','status','--porcelain=v1','-z','--untracked-files=all'],cwd=ROOT).decode('utf-8')
    changes=[{'status':line[:2],'path':line[3:]} for line in status.split('\0') if line]
    check('no_staging',all(item['status'][0] in {' ','?'} for item in changes))
    check('diff_whitespace',subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True).returncode==0)
    for relative in [item['path'] for item in changes if item['path'].endswith('.py') and (ROOT/item['path']).is_file()]:ast.parse((ROOT/relative).read_text(encoding='utf-8'))
    check('changed_python_syntax',True)
    check('formal_final_metadata_still_matches_verified_snapshot',snapshot(DEFAULT_DATABASE)==read(checks_dir/'stage2-4-migration.json')['after'])
    docs_changed=['docs/'+name for name in DOC_NAMES]
    reports=sorted(p.relative_to(ROOT).as_posix() for p in checks_dir.iterdir() if p.is_file() and (p.name.startswith('stage2-4-') or p.name.startswith('r20-') or p.name.startswith('source-state-r20-')))
    summary={'date':'2026-11-08','round':'R20','stage':'2-4','overall':'passed','next_unique_task':'2-5 — D-no-text真实推理适配；须用户指定，本轮停止',
        'source_files':changes,'documentation_files':docs_changed,'reports_and_inspection_images':reports,
        'ignored_local_artifacts':['.venv-parser','runtime/checks/parser-environment-seed.json','runtime/parsing','runtime/verification/r20'],
        'tests':{'backend':104,'frontend':25,'algorithm_cpu':4,'typecheck':'passed','production_build':'passed','provenance_coordinates':61,'geometry_and_failure':15,'actual_http':46,'formal_migration':19,'formal_anonymous_http':5,'final_protection':42},
        'results':{'real_uploaded_pdf_pages':11,'candidates':194,'new_page_encoding':0,'D_forward':0,'full_cached_features_checked':24,'formal_original_pages':13,'formal_revision':'0008_parsing'},
        'failures':'docs/checks/stage2-4-failures.json','open_blockers':[],'known_limits':['Only zero-rotation, zero-origin and CropBox=MediaBox geometry; rotated/cropped PDF region parsing is rejected, retrieval preserved.','Actual content sample is reused R19 uploaded5/6-page PDFs, not a new R20 upload or unseen evaluation. Different aspect ratios tested only with real blank geometry fixtures.','D, region HTTP endpoints, website highlighting/50%-150% scaling and official scoring remain unimplemented in this batch.','New docs are still ignored by original Git rules and need separate transfer. Local resource copying is not a portable wheel/installer.'],
        'document_checks':len(checks),'no_commit_or_push':'No staging/commit/push commands executed; project HEAD baseline was not recorded in preflight, so no fabricated before/after HEAD claim.'}
    summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    doc_path.write_text(json.dumps({'round':'R20','overall':'passed','checks':checks},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(checks)} document/scope checks passed; complete source/doc/report file list saved')


if __name__=='__main__':main()
