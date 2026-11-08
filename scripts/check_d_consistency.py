"""R21 frozen source_dev reference comparison; never read gold/prediction columns.

Original definitions are executed only in this offline verification namespace.
Production has no import or sys.path dependency on either research repository.
"""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from collections.abc import Sequence

import torch
from torch import nn
from torch.nn.functional import normalize

from backend.algorithms.d_adapter import DNoTextAdapter, tensor_sha
from backend.algorithms.d_core.layout import page_layout
from backend.algorithms.d_core.scoring import patch_iou_matrix,patch_scores,region_scores

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'layoutpatch'
OUT=ROOT/'runtime/verification/r21'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
    frozen=OUT/'dev-samples.json'
    if not frozen.exists():
        # The old environment supplies its existing parquet reader only. Its
        # stdout is captured here; it does not write to either old repository.
        program="""import polars as pl,json,pathlib
r=pathlib.Path('../layoutpatch')
m=json.loads((r/'artifacts/route_v2_data/d_nodes_dev_v1/manifest.json').read_text())
pages=sorted(m['pages'],key=lambda p:(p['doc_id'],p['page']))[:3]
assert all(p['role']=='source_dev' for p in pages)
u=pl.read_parquet(r/'artifacts/route_v2_data/regions_v1/units.parquet',columns=['doc_id','page','page_cache_id','query_id','role','page_size'])
c=pl.read_parquet(r/'artifacts/route_v2_data/regions_v1/candidates.parquet',columns=['doc_id','page','layout_id','bbox'])
out=[{'node':p,'unit':u.filter((pl.col('doc_id')==p['doc_id'])&(pl.col('page')==p['page'])).sort('query_id').row(0,named=True),'candidates':c.filter((pl.col('doc_id')==p['doc_id'])&(pl.col('page')==p['page'])).sort('layout_id').to_dicts()} for p in pages]
print(json.dumps(out,ensure_ascii=False))"""
        raw=subprocess.check_output([str(OLD/'.venv/Scripts/python.exe'),'-B','-c',program],cwd=ROOT,env={**os.environ,'PYTHONUTF8':'1'},text=True,encoding='utf-8')
        with frozen.open('x',encoding='utf-8') as stream:json.dump(json.loads(raw),stream,ensure_ascii=False,indent=2)
    samples=json.loads(frozen.read_text('utf-8'))
    input_paths=[OLD/'artifacts/route_v2_data/regions_v1/units.parquet',OLD/'artifacts/route_v2_data/regions_v1/candidates.parquet',OLD/'artifacts/route_v2_data/query_cache_v1/source_queries.pt']
    for sample in samples:
        input_paths.extend([OLD/'artifacts/route_v2_data/d_nodes_dev_v1'/sample['node']['file'],OLD/'artifacts/colpali/mmdocir_evaluation/vidore_colpali'/f"{sample['unit']['page_cache_id']}.pt"])
    inputs={p.relative_to(OLD).as_posix():digest(p) for p in input_paths}
    freeze=OUT/'dev-input-hashes.json'
    if freeze.exists():assert json.loads(freeze.read_text())==inputs
    else:freeze.write_text(json.dumps(inputs,indent=2)+'\n',encoding='utf-8')
    ns={'torch':torch,'nn':nn,'math':math,'Sequence':Sequence,'normalize':normalize,'GRID':32,'MODEL_SIZE':448,'D':128,'TOP_K':4,'GATE_BIAS':-3.0,'COORD_DIM':6,'UNK_TYPE_ID':0,'TEXT_DIM':1024,'PAGE_TOKENS':1031,'NUM_PATCHES':1024,
        'TYPE_TO_ID':{'UNK':0,'text':1,'title':2,'table':3,'image':4,'equation':5},
        '_TYPE_ALIASES':{'paragraph':'text','table_block':'table','figure':'image','interline_equation':'equation'}}
    source=ROOT.parent/'layoutpatch-evidence/src/layoutpatch'
    reference={}
    specs=[('layout/correspondence.py',['scale_bbox_to_model','clamp_bbox','patch_bbox','intersection_area','area','correspondence_row']),
        ('layout/schema.py',['canonical_layout_type']),('layout/nodes.py',['sinusoidal_coord','TextLayoutEncoder']),
        ('retrieval/fusion/sparse_fusion.py',['SparseLocalFusionV2']),('retrieval/colpali_layout.py',['split_page_embedding']),
        ('retrieval/route_v2_layout.py',['page_layout','LayoutPatchD']),('retrieval/route_v2_attribution.py',['InputAblatedD']),
        ('retrieval/route_v2_scoring.py',['valid_query','patch_scores','patch_iou_matrix','region_scores']),('evaluation/localization.py',['rank_candidates'])]
    for name,selected in specs:
        original=(source/name).read_text('utf-8');reference[name]=digest(source/name)
        definitions={n.name:ast.get_source_segment(original,n) for n in ast.parse(original).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
        exec(compile('from __future__ import annotations\n'+'\n\n'.join(definitions[n] for n in selected),str(source/name),'exec'),ns)
    ns['_CELLS']=torch.tensor([ns['patch_bbox'](i) for i in range(1024)],dtype=torch.float32)
    checkpoint=OLD/'runs/retrieval/route_v2_exp3_attribution/20261007_135013/D-no-text/seed_0_epoch_01.pt'
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    original=ns['InputAblatedD']('text').eval();original.load_state_dict(saved['state_dict'],strict=True)
    adapter=DNoTextAdapter(cache_root=OUT/'dev-unused-cache')
    query_cache=torch.load(OLD/'artifacts/route_v2_data/query_cache_v1/source_queries.pt',map_location='cpu',weights_only=True)
    results=[]
    for sample in samples:
        node,unit=sample['node'],sample['unit']
        assert unit['role']=='source_dev'
        path=OLD/'artifacts/route_v2_data/d_nodes_dev_v1'/node['file']
        assert digest(path)==node['sha256']
        payload=torch.load(path,map_location='cpu',weights_only=True)
        rows=payload['nodes'];ids=[r['layout_id'] for r in rows]
        assert ids==[r['layout_id'] for r in sample['candidates']]
        assert [r['bbox'] for r in rows]==[r['bbox'] for r in sample['candidates']]
        adapted=page_layout(rows,torch.zeros(len(rows),1024))
        for key in ('coords','types','mask','W_raw','W_attn','cover_mass'):
            torch.testing.assert_close(adapted[key],payload['layout'][key],atol=1e-6,rtol=1e-5)
        page=torch.load(OLD/'artifacts/colpali/mmdocir_evaluation/vidore_colpali'/f"{unit['page_cache_id']}.pt",map_location='cpu',weights_only=True)['embedding']
        assert tuple(page.shape)==(1031,128)
        p=page[:1024].float();q=query_cache['embeddings'][unit['query_id']].float()
        provenance=next(r for r in query_cache['provenance']['queries'] if r['query_id']==unit['query_id'])
        assert provenance['doc_id']==unit['doc_id'] and provenance['role']=='source_dev'
        with torch.inference_mode():
            before=original(p,payload['layout']);after=adapter.model(p,adapted)
            s0=ns['region_scores'](ns['patch_scores'](q,before),ns['patch_iou_matrix']([r['bbox'] for r in rows],unit['page_size']))
            s1=region_scores(patch_scores(q,after),patch_iou_matrix([r['bbox'] for r in rows],unit['page_size']))
        torch.testing.assert_close(after,before,atol=1e-6,rtol=1e-5)
        torch.testing.assert_close(s1,s0,atol=1e-6,rtol=1e-5)
        assert bool(torch.isfinite(s0).all()) and bool(torch.isfinite(s1).all())
        order0=ns['rank_candidates'](s0.tolist(),ids)
        order1=sorted(range(len(ids)),key=lambda i:(-float(s1[i]),ids[i]))
        assert order0==order1
        results.append({'doc_id':unit['doc_id'],'page':unit['page'],'query_id':unit['query_id'],'layout_ids':ids,
            'ranked_layout_ids':[ids[i] for i in order1],'pprime_max_abs':float((before-after).abs().max()),
            'score_max_abs':float((s0-s1).abs().max()),'pprime_sha256':tensor_sha(after),
            'scores_original':s0.tolist(),'scores_migrated':s1.tolist(),
            'near_ties':[[ids[a],ids[b]] for a,b in zip(order1,order1[1:]) if math.isclose(float(s1[a]),float(s1[b]),abs_tol=1e-6,rel_tol=1e-5)]})
    report={'round':'R21','overall':'passed','atol':1e-6,'rtol':1e-5,'dtype':'cpu-float32','samples':results,
        'inputs':inputs,'reference_sources':reference,'checkpoint_sha256':digest(checkpoint),'d_profile_sha256':adapter.profile_id,
        'reference_forwards':len(results),'migrated_forwards':len(results),
        'scope':'3 prespecified source_dev cache pairs, no gold/predictions/metrics; original AST definitions only in verification namespace, no production old-source imports; zero page/query encoding'}
    with (ROOT/'docs/checks/stage2-5-consistency.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'samples':len(results),'max_pprime_abs':max(r['pprime_max_abs'] for r in results),'max_score_abs':max(r['score_max_abs'] for r in results),'ranking_equal':True}))


if __name__=='__main__':main()
