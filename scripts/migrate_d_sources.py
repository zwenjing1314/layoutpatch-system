"""One-time controlled extraction of the frozen D inference dependency closure.

No training/evaluation CLI or datasets dependency is migrated. Existing files refuse overwrite.
"""
import ast
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent/'layoutpatch-evidence/src/layoutpatch'
TARGET = ROOT/'backend/algorithms/d_core'


def main():
    TARGET.mkdir(parents=True,exist_ok=False)
    specs = {
        'correspondence.py':('layout/correspondence.py',None,None),
        'nodes.py':('layout/nodes.py',None,None),
        'schema.py':('layout/schema.py',None,None),
        'colpali_layout.py':('retrieval/colpali_layout.py',None,None),
        'fusion.py':('retrieval/fusion/sparse_fusion.py',['SparseLocalFusionV2'],
            'import torch\nfrom torch import nn\nD = 128\nTOP_K = 4\nGATE_BIAS = -3.0\n'),
        'scoring.py':('retrieval/route_v2_scoring.py',['valid_query','patch_scores','patch_iou_matrix','region_scores'],
            'import math\nfrom collections.abc import Sequence\nimport torch\nfrom torch.nn.functional import normalize\nfrom .correspondence import GRID, clamp_bbox, patch_bbox, scale_bbox_to_model\n_CELLS = torch.tensor([patch_bbox(i) for i in range(GRID * GRID)], dtype=torch.float32)\n'),
        'layout.py':('retrieval/route_v2_layout.py',['page_layout','LayoutPatchD'],
            'import torch\nfrom torch import nn\nfrom .correspondence import clamp_bbox, correspondence_row, scale_bbox_to_model\nfrom .nodes import TextLayoutEncoder\nfrom .schema import TYPE_TO_ID, canonical_layout_type\nfrom .colpali_layout import split_page_embedding\nfrom .fusion import SparseLocalFusionV2\nTEXT_DIM = 1024\n'),
        'ablation.py':('retrieval/route_v2_attribution.py',['InputAblatedD'],
            'import torch\nfrom .layout import LayoutPatchD\n'),
    }
    provenance = {'source':'../layoutpatch-evidence','origin':'../layoutpatch','license':'No license supplied by source; local adaptation only; redistribution needs separate review.', 'files':{}}
    for name,(relative,selected,header) in specs.items():
        data=(SOURCE/relative).read_bytes();original=data.decode('utf-8')
        if selected is None:
            output=original.replace('from layoutpatch.layout.correspondence import GRID','from .correspondence import GRID')
        else:
            definitions={n.name:ast.get_source_segment(original,n) for n in ast.parse(original).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
            output='"""Frozen inference definitions extracted without arithmetic changes; see SOURCE.json."""\nfrom __future__ import annotations\n'+header+'\n\n'+'\n\n'.join(definitions[n] for n in selected)+'\n'
        (TARGET/name).write_text(output,encoding='utf-8')
        provenance['files'][name]={'source':relative,'source_sha256':hashlib.sha256(data).hexdigest(),'selected':selected or 'whole file','migrated_sha256':hashlib.sha256((TARGET/name).read_bytes()).hexdigest()}
    (TARGET/'__init__.py').write_text('"""Frozen D-no-text inference dependency closure; torch/model environment only."""\n',encoding='utf-8')
    (TARGET/'SOURCE.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    checkpoint=ROOT.parent/'layoutpatch/runs/retrieval/route_v2_exp3_attribution/20261007_135013/D-no-text/seed_0_epoch_01.pt'
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()=='18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b'
    dest=ROOT/'runtime/models/d-no-text/seed_0_epoch_01.pt'
    dest.parent.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(checkpoint,dest)
    print('Migrated 8 inference source files and verified local seed0/epoch1 copy; no downloads')


if __name__=='__main__':main()
