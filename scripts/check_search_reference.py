"""Compare actual HTTP/Qdrant results to CPU MaxSim and the official processor."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(input_path, output_path=None, round_id='R10'):
    os.environ['HF_HUB_OFFLINE']=os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    from colpali_engine.models import ColPaliProcessor
    from backend.algorithms.contracts import maxsim_scores
    torch.set_num_threads(4)
    cases=json.loads(input_path.read_text(encoding='utf-8'))
    cache=torch.load(ROOT/'runtime/verification/20261105-gpu-first/page_embeddings.pt',map_location='cpu',weights_only=True)
    features=dict(zip(cache['page_ids'],cache['embeddings'],strict=True))
    results=[]
    for case in cases:
        audit=json.loads(Path(case['audit']).read_text(encoding='utf-8'))
        query=torch.tensor(audit['vector'],dtype=torch.float32)
        ids=list(case['pages'])
        pages=[features[case['pages'][i]] for i in ids]
        direct=maxsim_scores(query,pages)
        official=ColPaliProcessor.score_multi_vector([query],[p.float() for p in pages],batch_size=16,device='cpu')[0]
        if not torch.allclose(direct,official,atol=1e-4,rtol=1e-5):
            raise AssertionError('CPU/reference disagreement')
        scores={i:float(v) for i,v in zip(ids,official,strict=True)}
        ordered=sorted(ids,key=lambda i:(-scores[i],i))
        returned=case['items']
        deltas=[abs(hit['page_score']-scores[hit['page_id']]) for hit in returned]
        for hit in returned:
            expected=scores[hit['page_id']]
            if abs(hit['page_score']-expected)>1e-4+1e-5*abs(expected):
                raise AssertionError('Qdrant score exceeds preset tolerance')
        # Tied scores may be returned in Qdrant's own order; require the same
        # top-k score multiset and strict order for non-tied comparisons.
        expected_scores=[scores[i] for i in ordered[:len(returned)]]
        actual_scores=[scores[h['page_id']] for h in returned]
        if any(abs(a-b)>1e-4+1e-5*abs(b) for a,b in zip(actual_scores,expected_scores,strict=True)):
            raise AssertionError('Filtered Top-k mismatch')
        strict=all(abs(scores[ordered[i]]-scores[ordered[i+1]])>1e-4+1e-5*abs(scores[ordered[i]]) for i in range(len(ordered)-1))
        if strict and [h['page_id'] for h in returned]!=ordered[:len(returned)]:
            raise AssertionError('Non-tied ranking mismatch')
        results.append({'name':case['name'],'authorized_pages':len(ids),'returned':len(returned),
                        'max_abs_diff':max(deltas,default=0),'top_k_matches':True,'non_tied':strict})
    report={'date':'2026-11-07','round':round_id,'atol':1e-4,'rtol':1e-5,'cases':results,
            'query_source':'actual live HTTP worker vectors, freshly encoded, not R03 query cache',
            'reference':'official ColPaliProcessor and CPU float32 MaxSim','overall':'passed'}
    target=output_path or ROOT/'docs/checks/stage1b-4-reference.json'
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--round',default='R10')
    args=parser.parse_args()
    main(args.input,args.output,args.round)
