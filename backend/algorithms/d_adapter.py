"""Frozen CPU float32 D-no-text inference. Import only in the model environment."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import shutil
import time
from uuid import uuid4

import torch

from .contracts import valid_embedding
from .d_core.ablation import InputAblatedD
from .d_core.layout import page_layout
from .d_core.scoring import patch_iou_matrix, patch_scores, region_scores

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT/'configs/d_no_text_local.json'


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tensor_sha(value):
    return sha(value.detach().cpu().float().contiguous().numpy().tobytes())


def load_profile():
    raw=PROFILE.read_bytes()
    profile=json.loads(raw)
    required={'schema':'d-no-text-local-v1','variant':'D-no-text','seed':0,'epoch':1,
        'checkpoint_sha256':'18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b',
        'precision':'cpu-float32','atol':1e-6,'rtol':1e-5,'tie':'score_desc_layout_id_asc',
        'text':'zeros_before_projection_no_text_model'}
    if any(profile.get(k)!=v for k,v in required.items()):
        raise ValueError('D frozen profile mismatch')
    for name,expected in profile['code_sha256'].items():
        path=(ROOT/name).resolve(strict=True)
        if not path.is_relative_to(ROOT/'backend/algorithms') or sha(path.read_bytes())!=expected:
            raise ValueError('D code identity mismatch')
    return profile,sha(raw)


def candidate_rows(candidates,identity):
    """Validate the full fixed set, before the legacy clamp or type fallback can run."""
    if not isinstance(candidates,list) or len(candidates)>2000 or sha(canonical(candidates).encode())!=identity['candidate_hash']:
        raise ValueError('Candidate set mismatch')
    rows=[];ids=set()
    width,height=identity['width_px'],identity['height_px']
    if type(width) is not int or type(height) is not int or min(width,height)<=0:
        raise ValueError('Invalid page size')
    for c in candidates:
        index=c['layout_id'];box=c['bbox']
        if (type(index) is not int or index<0 or index in ids or c['candidate_id']!=f"{identity['page_id']}:block:{index}"
                or c['type'] not in {'text','title','image','table','equation'}
                or not isinstance(box,list) or len(box)!=4
                or not all(type(v) in (int,float) and math.isfinite(v) for v in box)
                or not (0<=box[0]<box[2]<=width and 0<=box[1]<box[3]<=height)
                or c['coordinate_system']!='original_png_pixel_xyxy_top_left'
                or any(c[k]!=identity[k] for k in ('page_id','document_id','document_version_id','render_sha256','width_px','height_px','parser_profile_sha256','page_index','page_number'))):
            raise ValueError('Invalid candidate identity/geometry')
        ids.add(index)
        rows.append({'layout_id':index,'bbox':box,'page_size':[width,height],'type':c['type']})
    if [r['layout_id'] for r in rows]!=sorted(ids):
        raise ValueError('Candidate order mismatch')
    return rows


class DNoTextAdapter:
    def __init__(self,cache_root=None):
        self.profile,self.profile_id=load_profile()
        path=(ROOT/self.profile['checkpoint']).resolve(strict=True)
        if not path.is_relative_to(ROOT/'runtime/models'):
            raise ValueError('Checkpoint path outside local model store')
        self.checkpoint_path=path
        data=path.read_bytes()
        if sha(data)!=self.profile['checkpoint_sha256']:
            raise ValueError('Checkpoint hash mismatch')
        saved=torch.load(BytesIO(data),map_location='cpu',weights_only=True)
        if saved['seed']!=0 or saved['epoch']!=1:
            raise ValueError('Frozen checkpoint metadata mismatch')
        self.model=InputAblatedD('text').cpu().float().eval()
        self.model.load_state_dict(saved['state_dict'],strict=True)
        self.model.requires_grad_(False)
        if sum(p.numel() for p in self.model.parameters())!=273410 or not all(torch.isfinite(p).all() for p in self.model.parameters()):
            raise ValueError('Invalid frozen parameters')
        self.cache_root=(cache_root or ROOT/'runtime/regions/d-no-text').resolve()
        if not self.cache_root.is_relative_to(ROOT/'runtime'):
            raise ValueError('Cache outside runtime')
        self.cache_root.mkdir(parents=True,exist_ok=True)
        self.forward_count=0

    def check_identity(self):
        _,current=load_profile()
        if current!=self.profile_id or sha(self.checkpoint_path.read_bytes())!=self.profile['checkpoint_sha256']:
            raise ValueError('D identity changed')

    def prepare(self,request):
        self.check_identity()
        identity=request['identity']
        rows=candidate_rows(request['candidates'],identity)
        path=(ROOT/request['tensor_path']).resolve(strict=True)
        if not path.is_relative_to(ROOT/'runtime/corpus/ingest'):
            raise ValueError('Full page feature path invalid')
        data=path.read_bytes()
        if len(data)>4_000_000 or sha(data)!=identity['tensor_sha256']:
            raise ValueError('Full page feature hash mismatch')
        saved=torch.load(BytesIO(data),map_location='cpu',weights_only=True)
        if (saved['schema']!='full-page-features-v1' or saved['visual_patch_count']!=1024
                or saved['encoder_sha256']!=identity['encoder_sha256'] or saved['render_sha256']!=identity['render_sha256']
                or saved['embeddings'].dtype!=torch.bfloat16):
            raise ValueError('Full page feature identity mismatch')
        full=valid_embedding(saved['embeddings'],rows=1031)
        if tensor_sha(full)!=identity['embedding_sha256']:
            raise ValueError('Indexed full page embedding mismatch')
        patches=full[:1024].float().contiguous() # Never [7:] or budget sequences.
        layout=page_layout(rows,torch.zeros(len(rows),1024,dtype=torch.float32))
        cache_identity={'schema':'d-no-text-derived-v1','profile_sha256':self.profile_id,'inputs':identity}
        key=sha(canonical(cache_identity).encode())
        folder=self.cache_root/key
        hit=folder.exists();elapsed=0.0
        if hit:
            manifest=json.loads((folder/'manifest.json').read_text('utf-8'))
            data=(folder/'patches.pt').read_bytes()
            if manifest['identity']!=cache_identity or sha(data)!=manifest['file_sha256']:
                raise ValueError('Derived cache identity/hash mismatch')
            pprime=torch.load(BytesIO(data),weights_only=True,map_location='cpu')
            if tensor_sha(pprime)!=manifest['pprime_sha256']:
                raise ValueError('Derived cache tensor mismatch')
        else:
            start=time.perf_counter()
            with torch.inference_mode():
                pprime=self.model(patches,layout).contiguous()
            elapsed=(time.perf_counter()-start)*1000
            self.forward_count+=1
        if pprime.dtype!=torch.float32:
            raise ValueError('Derived cache must be float32')
        pprime=valid_embedding(pprime,rows=1024).float()
        if not hit:
            temporary=self.cache_root/('tmp-'+uuid4().hex)
            temporary.mkdir()
            try:
                torch.save(pprime,temporary/'patches.pt')
                manifest={'identity':cache_identity,'file_sha256':sha((temporary/'patches.pt').read_bytes()),
                    'pprime_sha256':tensor_sha(pprime),'dtype':'float32','shape':[1024,128],
                    'checkpoint_sha256':self.profile['checkpoint_sha256'],'forward_ms':elapsed}
                (temporary/'manifest.json').write_text(canonical(manifest),encoding='utf-8')
                # Same worker serializes access. Concurrent publishers refuse overwrite.
                os.rename(temporary,folder)
            finally:
                if temporary.exists():shutil.rmtree(temporary)
        return rows,pprime,{'cache_key':key,'cache_hit':hit,'pprime_sha256':tensor_sha(pprime),
            'd_forward_count':self.forward_count,'d_forward_ms':elapsed,'d_profile_sha256':self.profile_id,
            'checkpoint_sha256':self.profile['checkpoint_sha256'],'strict_load':True,'parameters':273410}

    def rank(self,request,query):
        valid_embedding(query)
        rows,pprime,audit=self.prepare(request)
        if not rows:
            return {'status':'no_candidates','rankings':[],**audit}
        with torch.inference_mode():
            scores=region_scores(patch_scores(query,pprime),patch_iou_matrix([r['bbox'] for r in rows],rows[0]['page_size']))
        if not bool(torch.isfinite(scores).all()):
            raise ValueError('Nonfinite region scores')
        order=sorted(range(len(rows)),key=lambda i:(-float(scores[i]),rows[i]['layout_id']))
        near=[]
        rankings=[]
        for rank,i in enumerate(order,1):
            rankings.append({'candidate_id':request['candidates'][i]['candidate_id'],'layout_id':rows[i]['layout_id'],'rank':rank,'score':float(scores[i])})
            if rank>1 and math.isclose(float(scores[order[rank-2]]),float(scores[i]),abs_tol=1e-6,rel_tol=1e-5):
                near.append([rows[order[rank-2]]['layout_id'],rows[i]['layout_id']])
        return {'status':'ready','rankings':rankings,'near_ties':near,**audit}
