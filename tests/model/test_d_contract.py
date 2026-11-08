"""Meaningful synthetic D/cache failure boundaries; run in frozen model venv."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest
import torch

from backend.algorithms.d_adapter import ROOT,DNoTextAdapter,canonical,sha,tensor_sha,candidate_rows


@pytest.fixture
def inputs():
    torch.set_num_threads(4)
    parent=ROOT/'runtime/corpus/ingest';parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='r21-d-fixture-',dir=parent) as name:
        folder=Path(name)
        full=torch.nn.functional.normalize(torch.randn(1031,128),dim=-1).bfloat16()
        tensor=folder/'full.pt';torch.save({'schema':'full-page-features-v1','visual_patch_count':1024,'encoder_sha256':'e'*64,'render_sha256':'r'*64,'embeddings':full},tensor)
        identity={'page_id':'p','document_id':'d','document_version_id':'v','page_index':0,'page_number':1,'width_px':1000,'height_px':1500,
            'render_sha256':'r'*64,'parser_profile_sha256':'m'*64,'encoder_sha256':'e'*64,'tensor_sha256':sha(tensor.read_bytes()),'embedding_sha256':tensor_sha(full)}
        candidates=[{**identity,'candidate_id':f'p:block:{i}','layout_id':i,'bbox':[20,30,600,800],'type':'text','coordinate_system':'original_png_pixel_xyxy_top_left'} for i in (2,5)]
        identity['candidate_hash']=sha(canonical(candidates).encode())
        request={'identity':identity,'candidates':candidates,'tensor_path':tensor.relative_to(ROOT).as_posix()}
        yield DNoTextAdapter(cache_root=folder/'cache'),request,full,tensor


def test_cache_reuses_only_document_features_and_exact_ties_use_layout_id(inputs):
    engine,request,full,_=inputs;q=torch.eye(128)[:3]
    first=engine.rank(request,q);second=engine.rank(request,torch.eye(128)[4:8])
    assert not first['cache_hit'] and second['cache_hit'] and engine.forward_count==1
    assert [r['layout_id'] for r in first['rankings']]==[2,5]
    assert first['rankings'][0]['score']==first['rankings'][1]['score']
    assert first['near_ties']==[[2,5]]
    assert torch.equal(full,torch.load(ROOT/request['tensor_path'],weights_only=True)['embeddings'])


def test_text_is_ablated_before_projection_and_full_sequence_is_not_modified(inputs):
    engine,request,full,_=inputs
    from backend.algorithms.d_core.layout import page_layout
    rows=candidate_rows(request['candidates'],request['identity'])
    layout=page_layout(rows,torch.randn(2,1024));zero=page_layout(rows,torch.zeros(2,1024))
    with torch.inference_mode():
        assert torch.equal(engine.model(full[:1024].float(),layout),engine.model(full[:1024].float(),zero))


def test_candidate_identity_geometry_type_order_and_hash_fail_closed(inputs):
    engine,request,_,_=inputs
    for change in (lambda r:r['candidates'][0].update(type='unknown'),lambda r:r['candidates'][0].update(bbox=[0,0,float('nan'),10]),
        lambda r:r['candidates'][0].update(bbox=[-1,0,20,20]),lambda r:r['candidates'].reverse(),
        lambda r:r['candidates'][0].update(page_id='other'),lambda r:r['candidates'][0].update(layout_id=True)):
        bad=deepcopy(request);change(bad)
        if all(not isinstance(v,float) or torch.isfinite(torch.tensor(v)) for v in bad['candidates'][0]['bbox']):
            bad['identity']['candidate_hash']=sha(canonical(bad['candidates']).encode())
        with pytest.raises(ValueError):engine.rank(bad,torch.eye(128)[:2])


def test_compressed_feature_or_bad_hash_or_index_identity_rejected(inputs):
    engine,request,full,tensor=inputs
    for content in (full[:128],full.float(),torch.full_like(full,float('nan'))):
        saved=torch.load(tensor,weights_only=True);saved['embeddings']=content;torch.save(saved,tensor)
        bad=deepcopy(request);bad['identity']['tensor_sha256']=sha(tensor.read_bytes())
        with pytest.raises(ValueError):engine.rank(bad,torch.eye(128)[:2])
    bad=deepcopy(request);bad['identity']['tensor_sha256']='0'*64
    with pytest.raises(ValueError):engine.rank(bad,torch.eye(128)[:2])


def test_corrupt_cache_is_rejected_without_overwrite(inputs):
    engine,request,_,_=inputs
    result=engine.rank(request,torch.eye(128)[:2]);path=engine.cache_root/result['cache_key']/'patches.pt'
    path.write_bytes(b'corrupt-cache');before=path.read_bytes()
    with pytest.raises(ValueError):engine.rank(request,torch.eye(128)[:2])
    assert path.read_bytes()==before and engine.forward_count==1


def test_nonfinite_region_output_never_returned(inputs):
    engine,request,_,_=inputs
    with patch('backend.algorithms.d_adapter.region_scores',return_value=torch.tensor([float('inf'),0.0])):
        with pytest.raises(ValueError,match='Nonfinite'):engine.rank(request,torch.eye(128)[:2])
    with pytest.raises(ValueError):engine.rank(request,torch.zeros(2,128))


def test_checkpoint_hash_and_state_dict_are_strict(inputs):
    engine,request,_,_=inputs
    original_load=torch.load
    def missing_parameter(*args,**kwargs):
        result=original_load(*args,**kwargs)
        if isinstance(result,dict) and 'state_dict' in result:result['state_dict'].pop(next(iter(result['state_dict'])))
        return result
    with patch('backend.algorithms.d_adapter.torch.load',side_effect=missing_parameter):
        with pytest.raises(RuntimeError):DNoTextAdapter(cache_root=engine.cache_root)
    original_read=Path.read_bytes
    def wrong_checkpoint(path):
        return b'wrong' if path==engine.checkpoint_path else original_read(path)
    with patch.object(Path,'read_bytes',wrong_checkpoint):
        with pytest.raises(ValueError,match='Checkpoint hash'):DNoTextAdapter(cache_root=engine.cache_root)


def test_candidate_or_model_identity_does_not_reuse_stale_cache(inputs):
    engine,request,_,_=inputs;q=torch.eye(128)[:2]
    first=engine.rank(request,q)
    request=deepcopy(request);request['candidates'][0]['bbox']=[30,40,650,900]
    request['identity']['candidate_hash']=sha(canonical(request['candidates']).encode())
    second=engine.rank(request,q)
    assert first['cache_key']!=second['cache_key'] and not second['cache_hit'] and engine.forward_count==2
    engine.profile_id='changed'
    with pytest.raises(ValueError,match='identity changed'):engine.rank(request,q)


def test_empty_candidates_remain_empty_with_no_invented_regions(inputs):
    engine,request,_,_=inputs
    request['candidates']=[];request['identity']['candidate_hash']=sha(b'[]')
    result=engine.rank(request,torch.eye(128)[:2])
    assert result['status']=='no_candidates' and result['rankings']==[]
