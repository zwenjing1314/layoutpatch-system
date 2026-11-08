"""R20 CPU-only check of already existing full-page caches, with no encoding or file mutation."""
import json
import sqlite3
from pathlib import Path
import hashlib


def main():
    import torch
    root=Path(__file__).resolve().parents[1]
    paths={}
    for relative in ('runtime/verification/r15/real-attempt2/metadata.sqlite3','runtime/verification/r19/ui/metadata.sqlite3'):
        with sqlite3.connect(f'file:{(root/relative).as_posix()}?mode=ro',uri=True) as db:
            for row in db.execute('SELECT tensor_path,tensor_sha256,export_path,export_sha256,encoder_sha256 FROM page_features'):
                paths[row[0]]=row
    # Include the genuinely computed R19 cancelled attempt, but do not call it active.
    for audit in (root/'runtime/verification/r19/ui/pages').glob('*.json'):
        row=json.loads(audit.read_text());paths[row['tensor_path']]=(row['tensor_path'],row['tensor_sha256'],row['export_path'],row['export_sha256'],row['profile_sha256'])
    checked=[]
    for tensor_path,tensor_sha,export_path,export_sha,encoder_sha in paths.values():
        data=(root/tensor_path).read_bytes();export=(root/export_path).read_bytes()
        assert hashlib.sha256(data).hexdigest()==tensor_sha and hashlib.sha256(export).hexdigest()==export_sha
        saved=torch.load(root/tensor_path,map_location='cpu',weights_only=True);tensor=saved['embeddings']
        assert tensor.shape==(1031,128) and tensor.dtype==torch.bfloat16 and torch.isfinite(tensor).all()
        assert saved['schema']=='full-page-features-v1' and saved['visual_patch_count']==1024 and saved['encoder_sha256']==encoder_sha
        exported=torch.tensor(json.loads(export),dtype=torch.float32)
        assert torch.equal(tensor.float(),exported)
        checked.append({'path':tensor_path,'tensor_sha256':tensor_sha,'export_sha256':export_sha,'shape':[1031,128],'dtype':'bfloat16','patches':1024})
    target=root/'docs/checks/stage2-4-features.json'
    with target.open('x',encoding='utf-8') as stream:json.dump({'round':'R20','overall':'passed','checked_count':len(checked),'tensors':checked,'scope':'Existing R15/R19 full tensors including5 cancelled R19 attempts; new CPU checks only, zero page encoding and no D input'},stream,ensure_ascii=False,indent=2)
    print(f'R20 CPU verified {len(checked)} existing full tensors and exact float32 exports; no page encoding')


if __name__=='__main__':main()
