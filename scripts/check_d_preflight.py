"""R21 fresh read-only baseline; never print credentials or query text."""
from contextlib import closing
import hashlib
import importlib.metadata as metadata
import json
import sqlite3
import subprocess

from backend.db.connection import ROOT, DEFAULT_DATABASE
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.check_selection_http import dynamic_fingerprint

OUT = ROOT / 'runtime/verification/r21'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect(DEFAULT_DATABASE)) as source, closing(sqlite3.connect(OUT/'metadata-before.sqlite3')) as target:
        source.backup(target)
        collection = source.execute('SELECT collection_name FROM index_generations WHERE id=(SELECT active_index_id FROM system_state WHERE id=1)').fetchone()[0]
    reused = ROOT/'runtime/verification/r19/ui/metadata.sqlite3'
    with closing(sqlite3.connect(f'file:{reused.as_posix()}?mode=ro', uri=True)) as db:
        rc, count = db.execute('SELECT collection_name,page_count FROM index_generations WHERE id=(SELECT active_index_id FROM system_state WHERE id=1)').fetchone()
        files = [ROOT/p for r in db.execute('SELECT tensor_path,export_path FROM page_features') for p in r]
    sources = ('retrieval/route_v2_layout.py','retrieval/route_v2_attribution.py','retrieval/route_v2_scoring.py',
               'retrieval/colpali_layout.py','layout/nodes.py','layout/correspondence.py','layout/schema.py','retrieval/fusion/sparse_fusion.py')
    source_hashes = {name: {repo: digest(ROOT.parent/repo/'src/layoutpatch'/name) for repo in ('layoutpatch','layoutpatch-evidence')} for name in sources}
    old = ROOT.parent/'layoutpatch'
    resources = [old/'runs/retrieval/route_v2_exp3_attribution/20261007_135013/D-no-text/seed_0_epoch_01.pt',
        old/'runs/retrieval/route_v2_exp3_attribution/20261007_135013/checkpoint_selection.json',
        old/'artifacts/route_v2_external/preparation_v1/20261007_152240/weights.json',
        old/'configs/experiments/route_v2_exp2_D.yaml',old/'configs/experiments/route_v2_exp3_attribution.yaml',
        old/'artifacts/route_v2_data/d_nodes_dev_v1/manifest.json',old/'artifacts/route_v2_data/query_cache_v1/source_queries.pt']
    protected = [ROOT/'.gitignore',*sorted((ROOT/'docs/过程记录').glob('0[1-6]*')),
        *sorted((ROOT/'backend/algorithms').glob('*.py')),*sorted(ROOT.glob('requirements-*')),ROOT/'configs/colpali_local.json',ROOT/'frontend/package.json',ROOT/'frontend/yarn.lock']
    ps = 'Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -In 3000,8000,8001,6333 | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress'
    report = {'round':'R21','date':'2026-11-08','stage':'2-5','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'initial_status':subprocess.check_output(['git','status','--short'],text=True),
        'database':snapshot(DEFAULT_DATABASE),'collection':collection,'qdrant':vector_fingerprint(collection),
        'r19_source':snapshot(reused),'r20_source':snapshot(ROOT/'runtime/verification/r20/metadata.sqlite3'),
        'reused_collection':rc,'reused_count':count,'reused_qdrant':dynamic_fingerprint(rc,count),
        'features':{p.relative_to(ROOT).as_posix():digest(p) for p in files},'protected':{p.relative_to(ROOT).as_posix():digest(p) for p in protected if p.is_file()},
        'sources':source_hashes,'resources':{p.relative_to(ROOT.parent).as_posix():digest(p) for p in resources},
        'ports':json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True)),
        'web_packages':sorted((d.metadata['Name'],d.version) for d in metadata.distributions()),
        'precision':{'device':'cpu','dtype':'float32','threads':4,'deterministic':True,'atol':1e-6,'rtol':1e-5,
                     'ranking':'descending score, ascending integer layout_id on exact tie',
                     'near_tie':'adjacent scores isclose(atol=1e-6,rtol=1e-5); report only, never reorder'},
        'sample_rule':'first 3 source_dev pages by (doc_id,page) in frozen node manifest, first query_id mapped to each page; no gold or prediction input',
        'scope':'R19 uploaded PDFs and R20 real candidates reused read-only; no new upload, parser or page encoding. Other visible project chats notLoaded at prior initial inventory.'}
    (ROOT/'docs/checks/stage2-5-preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'revision':report['database']['revision'],'counts':{k:v['count'] for k,v in report['database']['tables'].items()},'source_pairs_equal':all(len(set(v.values()))==1 for v in source_hashes.values()),'baseline':'stage2-5-preflight.json'}))


if __name__=='__main__':main()
