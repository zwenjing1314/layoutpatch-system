"""R21 independent CPU reference of all real-query receipts and durable cache replay."""
import ast
import hashlib
import json
import math
from pathlib import Path
from collections.abc import Sequence

import torch
from torch import nn
from torch.nn.functional import normalize

from backend.algorithms.d_adapter import DNoTextAdapter,tensor_sha

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/verification/r21'


def main():
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
    source=ROOT.parent/'layoutpatch-evidence/src/layoutpatch'
    ns={'torch':torch,'nn':nn,'math':math,'Sequence':Sequence,'normalize':normalize,'GRID':32,'MODEL_SIZE':448,'D':128,'TOP_K':4,'GATE_BIAS':-3.0,'COORD_DIM':6,'UNK_TYPE_ID':0,'TEXT_DIM':1024,
        'PAGE_TOKENS':1031,'NUM_PATCHES':1024,'TYPE_TO_ID':{'UNK':0,'text':1,'title':2,'table':3,'image':4,'equation':5},
        '_TYPE_ALIASES':{'paragraph':'text','table_block':'table','figure':'image','interline_equation':'equation'}}
    specs=[('layout/correspondence.py',['scale_bbox_to_model','clamp_bbox','patch_bbox','intersection_area','area','correspondence_row']),
        ('layout/schema.py',['canonical_layout_type']),('layout/nodes.py',['sinusoidal_coord','TextLayoutEncoder']),('retrieval/fusion/sparse_fusion.py',['SparseLocalFusionV2']),
        ('retrieval/colpali_layout.py',['split_page_embedding']),('retrieval/route_v2_layout.py',['page_layout','LayoutPatchD']),('retrieval/route_v2_attribution.py',['InputAblatedD']),
        ('retrieval/route_v2_scoring.py',['valid_query','patch_scores','patch_iou_matrix','region_scores']),('evaluation/localization.py',['rank_candidates'])]
    for name,selected in specs:
        text=(source/name).read_text('utf-8');definitions={n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        exec(compile('from __future__ import annotations\n'+'\n\n'.join(definitions[n] for n in selected),str(source/name),'exec'),ns)
    ns['_CELLS']=torch.tensor([ns['patch_bbox'](i) for i in range(1024)],dtype=torch.float32)
    original=ns['InputAblatedD']('text').eval()
    state=torch.load(ROOT/'runtime/models/d-no-text/seed_0_epoch_01.pt',map_location='cpu',weights_only=True)
    original.load_state_dict(state['state_dict'],strict=True)
    real=json.loads((ROOT/'docs/checks/stage2-5-real.json').read_text('utf-8'))
    requests={p['result']['cache_key']:json.loads((OUT/'requests'/f"{p['owner']}-{p['page_number']}.json").read_text('utf-8')) for p in real['pages']}
    results=[];receipts=sorted((OUT/'regions').glob('*.json'))
    assert len(receipts)==12
    for path in receipts:
        audit=json.loads(path.read_text('utf-8'));result=audit['regions'];request=requests[result['cache_key']]
        assert audit['network_attempts']==0 and result['checkpoint_sha256']=='18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b'
        full=torch.load(ROOT/request['tensor_path'],map_location='cpu',weights_only=True)['embeddings']
        q=torch.tensor(audit['vector'],dtype=torch.float32)
        rows=[{'layout_id':c['layout_id'],'bbox':c['bbox'],'page_size':[c['width_px'],c['height_px']],'type':c['type']} for c in request['candidates']]
        layout=ns['page_layout'](rows,torch.zeros(len(rows),1024))
        with torch.inference_mode():
            before=original(full[:1024].float(),layout)
            scores=ns['region_scores'](ns['patch_scores'](q,before),ns['patch_iou_matrix']([c['bbox'] for c in rows],rows[0]['page_size']))
        cached=torch.load(ROOT/'runtime/regions/d-no-text'/result['cache_key']/'patches.pt',map_location='cpu',weights_only=True)
        torch.testing.assert_close(cached,before,atol=1e-6,rtol=1e-5)
        order=ns['rank_candidates'](scores.tolist(),[r['layout_id'] for r in rows])
        assert [rows[i]['layout_id'] for i in order]==[r['layout_id'] for r in result['rankings']]
        migrated=torch.tensor([r['score'] for r in result['rankings']])
        reference=scores[order]
        torch.testing.assert_close(migrated,reference,atol=1e-6,rtol=1e-5)
        results.append({'query_sha256':audit['query_sha256'],'cache_key':result['cache_key'],'candidate_count':len(rows),
            'pprime_max_abs':float((before-cached).abs().max()),'score_max_abs':float((reference-migrated).abs().max()),
            'pprime_sha256':tensor_sha(before),'ranking_equal':True,'near_ties':result['near_ties']})
    adapter=DNoTextAdapter()
    # Fresh process/instance, same input: disk cache only; no D forward.
    replay=adapter.rank(request,q)
    assert replay['cache_hit'] and adapter.forward_count==0 and replay['rankings']==result['rankings']
    report={'round':'R21','overall':'passed','atol':1e-6,'rtol':1e-5,'dtype':'cpu-float32','results':results,
        'reference_forwards':len(results),'durable_cache_replay':{'cache_hit':True,'d_forwards':0,'rankings_equal':True},
        'scope':'All 12 actual new-query vectors against original source definitions; no gold/predictions/effectiveness metric'}
    with (ROOT/'docs/checks/stage2-5-reference.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'actual_query_receipts':len(results),'max_pprime_abs':max(r['pprime_max_abs'] for r in results),'max_score_abs':max(r['score_max_abs'] for r in results),'cache_restart_forward_count':0}))


if __name__=='__main__':main()
