"""R21 reviewable file manifest and paired learning-record/link checks."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text('utf-8'))


def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,text=True,encoding='utf-8').strip()


def main():
    report_dir=ROOT/'docs/checks'
    docs=['docs/AI交接.md','docs/progress.md','docs/testing.md','docs/requirements.md','docs/architecture.md','docs/interfaces.md',
        'docs/项目开发阶段规划与任务.md','docs/阶段2新窗口接手指南.md','docs/source-audit.md','docs/stage2-5-runbook.md',
        'docs/过程记录/07_2技术操作详解.md','docs/过程记录/08_2逐步口述稿.md']
    reports=[p.relative_to(ROOT).as_posix() for p in sorted(report_dir.glob('stage2-5-*.json'))]
    reports += ['docs/checks/source-state-r21-before.json','docs/checks/source-state-r21-final.json','docs/checks/stage2-5-verification.json','docs/checks/r21-document-checks.json']
    code=sorted(set(git('diff','--name-only').splitlines()+git('ls-files','--others','--exclude-standard').splitlines())-set(docs))
    baseline=read(report_dir/'stage2-5-preflight.json')
    summary={'round':'R21','date':'2026-11-08','stage':'2-5','overall':'passed','next_only_task':'2-6 授权区域接口、高亮与阶段2整体验收；等用户指定',
        'modified_or_created_files':{'code_and_config':code,'documentation':docs,'reports':reports,
            'private_runtime':'runtime/verification/r21 (online backup/clone/requests/query vectors/test logs), runtime/models/d-no-text local checkpoint copy, runtime/regions/d-no-text immutable Pprime caches; not source-control artifacts'},
        'actual_checks':{'source_checks':22,'web_tests':112,'model_d_contracts':9,'original_model_contracts':4,'original_chain_actual_asgi':32,'final_protection':65,
            'development_pages':3,'real_mineru_pages':11,'real_candidates':194,'new_region_queries':12,'old_chain_new_queries':4,
            'development_and_actual_q_reference_max_abs':0,'d_actual_forwards':11,'atol':1e-6,'rtol':1e-5},
        'formal_database':'0008_parsing, all original table fingerprints unchanged, 2 documents/13 pages, parser tables empty',
        'schema_api_sdk_frontend':'unchanged; no region HTTP or highlight','failed_or_blocked':'All2-5 failures resolved/isolated; no current batch blocker. Historical old-environment write restriction remains outside batch.',
        'effectiveness_claim':False,'new_page_encoding':0,'new_mineru_parsing':0,'downloads':0,'training':0,
        'git_head_unchanged':git('rev-parse','HEAD')==baseline['head'],'staged_diff_empty':not git('diff','--cached','--name-only'),
        'no_commit_or_push':'No staging/commit/push commands used; HEAD unchanged; all modifications remain local',
        'limits':['Reused R19 real uploads and R20 real parser candidates; not R21 new uploads or unseen test set.',
            'Internal caller supplies authenticated principal;2-6 must revalidate actual session before/after inference.',
            'No region HTTP/SDK/browser highlight/scaling/accuracy/capacity/full-stage2 acceptance.',
            'Formal services retained; only anonymous localhost probes; no formal credentials used.',
            'New docs and learning records follow existing ignore rules and need separate transfer.']}
    with (report_dir/'stage2-5-verification.json').open('x',encoding='utf-8') as stream:json.dump(summary,stream,ensure_ascii=False,indent=2)
    checks=[]
    def check(name,value,**detail):
        checks.append({'name':name,'passed':bool(value),**detail})
        assert value,name
    check('head_and_index_unchanged',summary['git_head_unchanged'] and summary['staged_diff_empty'])
    technical=(ROOT/docs[-2]).read_text('utf-8');spoken=(ROOT/docs[-1]).read_text('utf-8')
    blocks=re.findall(r'## 2026-11-08｜R21｜2-5｜(S\d+)([^\n]*)\n\n(.*?)(?=\n## |\Z)',spoken,re.S)
    check('six_paired_steps',[s for s,_,_ in blocks]==['S01','S02','S03','S04','S05','S06'])
    for step,title,body in blocks:
        check(step+'_date_round_step_title_matches',f'## 2026-11-08｜R21｜2-5｜{step}{title}' in technical)
        check(step+'_spoken60_100_characters',60<=len(body.strip())<=100,characters=len(body.strip()))
    for name in docs:
        text=(ROOT/name).read_text('utf-8')
        # Only new R21 links; historical relative references retain their scope.
        if 'R21' in text and name!='docs/stage2-5-runbook.md':
            start=text.find('R21');end=text.find('\n## ',start)
            text=text[start:end if end!=-1 else len(text)]
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if target.startswith(('http:','https:','#')):continue
            target=target.split('#',1)[0]
            check('local_link_'+name+'_'+target,(ROOT/name).parent.joinpath(target).is_file())
    for name in code+docs:
        check('file_exists_'+name,(ROOT/name).is_file())
    report={'round':'R21','overall':'passed','checks':checks,'source_files_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in code},
        'scope':'R21 new documentation links/paired60-100-character learning steps and reviewable file list; old documentation/history retained'}
    with (report_dir/'r21-document-checks.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'document_checks':len(checks),'file_counts':{'code':len(code),'docs':len(docs),'reports':len(reports)},'head_unchanged':summary['git_head_unchanged'],'staged_diff_empty':summary['staged_diff_empty']}))


if __name__=='__main__':main()
