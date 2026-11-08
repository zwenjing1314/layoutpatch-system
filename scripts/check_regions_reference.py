"""R22 same-run Q versus read-only original D definitions on new MinerU candidates."""
import ast
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from collections.abc import Sequence
import torch
from torch import nn
from torch.nn.functional import normalize

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/verification/r22'


def read(path):return json.loads(path.read_text('utf-8'))


def main():
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
    source=ROOT.parent/'layoutpatch-evidence/src/layoutpatch'
    ns={'torch':torch,'nn':nn,'math':math,'Sequence':Sequence,'normalize':normalize,'GRID':32,'MODEL_SIZE':448,'D':128,'TOP_K':4,'GATE_BIAS':-3.0,'COORD_DIM':6,'UNK_TYPE_ID':0,'TEXT_DIM':1024,
        'PAGE_TOKENS':1031,'NUM_PATCHES':1024,'TYPE_TO_ID':{'UNK':0,'text':1,'title':2,'table':3,'image':4,'equation':5},'_TYPE_ALIASES':{'paragraph':'text','table_block':'table','figure':'image','interline_equation':'equation'}}
    specs=[('layout/correspondence.py',['scale_bbox_to_model','clamp_bbox','patch_bbox','intersection_area','area','correspondence_row']),('layout/schema.py',['canonical_layout_type']),('layout/nodes.py',['sinusoidal_coord','TextLayoutEncoder']),('retrieval/fusion/sparse_fusion.py',['SparseLocalFusionV2']),('retrieval/colpali_layout.py',['split_page_embedding']),('retrieval/route_v2_layout.py',['page_layout','LayoutPatchD']),('retrieval/route_v2_attribution.py',['InputAblatedD']),('retrieval/route_v2_scoring.py',['valid_query','patch_scores','patch_iou_matrix','region_scores']),('evaluation/localization.py',['rank_candidates'])]
    for name,names in specs:
        text=(source/name).read_text('utf-8');definitions={n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        exec(compile('from __future__ import annotations\n'+'\n\n'.join(definitions[n] for n in names),str(source/name),'exec'),ns)
    ns['_CELLS']=torch.tensor([ns['patch_bbox'](i) for i in range(1024)],dtype=torch.float32)
    original=ns['InputAblatedD']('text').eval();weight=ROOT/'runtime/models/d-no-text/seed_0_epoch_01.pt'
    assert hashlib.sha256(weight.read_bytes()).hexdigest()=='18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b'
    original.load_state_dict(torch.load(weight,map_location='cpu',weights_only=True)['state_dict'],strict=True)
    reports=[]
    with sqlite3.connect(f'file:{(OUT/"metadata.sqlite3").as_posix()}?mode=ro',uri=True) as db:
        for path in sorted((OUT/'region').glob('*.json')):
            audit=read(path);result=audit['regions'];folder=ROOT/'runtime/regions/d-no-text'/result['cache_key'];identity=read(folder/'manifest.json')['identity']['inputs']
            candidates=json.loads(db.execute('select candidates_json from page_parses where task_id=? and page_id=?',(identity['parsing_task_id'],identity['page_id'])).fetchone()[0])
            tensor_path=db.execute('select tensor_path from page_features where page_id=?',(identity['page_id'],)).fetchone()[0]
            full=torch.load(ROOT/tensor_path,map_location='cpu',weights_only=True)['embeddings'];assert full.shape==(1031,128) and full.dtype==torch.bfloat16
            q=torch.tensor(audit['vector'],dtype=torch.float32)
            rows=[{'layout_id':c['layout_id'],'bbox':c['bbox'],'page_size':[c['width_px'],c['height_px']],'type':c['type']} for c in candidates]
            layout=ns['page_layout'](rows,torch.zeros(len(rows),1024))
            with torch.inference_mode():
                pprime=original(full[:1024].float(),layout)
                scores=ns['region_scores'](ns['patch_scores'](q,pprime),ns['patch_iou_matrix']([r['bbox'] for r in rows],rows[0]['page_size']))
            cached=torch.load(folder/'patches.pt',weights_only=True,map_location='cpu');torch.testing.assert_close(cached,pprime,atol=1e-6,rtol=1e-5)
            order=ns['rank_candidates'](scores.tolist(),[r['layout_id'] for r in rows]);ranked=result['rankings']
            assert [rows[i]['layout_id'] for i in order]==[r['layout_id'] for r in ranked]
            migrated=torch.tensor([r['score'] for r in ranked]);torch.testing.assert_close(migrated,scores[order],atol=1e-6,rtol=1e-5)
            reports.append({'audit':path.relative_to(ROOT).as_posix(),'page_id':identity['page_id'],'query_sha256':audit['query_sha256'],'candidate_count':len(rows),'pprime_max_abs':float((pprime-cached).abs().max()),'score_max_abs':float((migrated-scores[order]).abs().max()),'ranking_equal':True,'near_ties':result['near_ties'],'cache_hit':result['cache_hit'],'d_forward_ms':result['d_forward_ms']})
    assert reports
    report={'round':'R22','overall':'passed','atol':1e-6,'rtol':1e-5,'cpu_threads':4,'dtype':'float32','results':reports,'reference_forwards':len(reports),'limits':'Original definitions only, no gold/prediction input; same actual query tensors and complete new-PDF candidates. No localization accuracy claim. Fixed source_dev three-page check is R21 historical, not rerun here.'}
    target=ROOT/'docs/checks/stage2-6-D-reference.json';assert not target.exists();target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Original D same-Q reference',len(reports),'passed; max score delta',max(r['score_max_abs'] for r in reports))


if __name__=='__main__':main()
