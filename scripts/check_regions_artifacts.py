"""R22 full BF16/float32 exports and real MinerU/D receipts; model environment only."""
import json
import hashlib
import sqlite3
from collections import Counter
from pathlib import Path

import torch
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/verification/r22'
STATE=OUT/'state.json'
DATABASE=OUT/'metadata.sqlite3'
def read(path):return json.loads(path.read_text('utf-8'))
def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

class Row(dict):
    def __getattr__(self,key):return self[key]


def main():
    state=read(STATE);pages=[];types=Counter();calls=0;seconds=0;receipts=[]
    with sqlite3.connect(f'file:{DATABASE.as_posix()}?mode=ro',uri=True) as db:
        db.row_factory=lambda cur,row:Row(zip([x[0] for x in cur.description],row))
        for spec in state['selected']:
            doc=db.execute('select * from documents where id=?',(spec['document_id'],)).fetchone();version=db.execute('select * from document_versions where id=?',(spec['document_version_id'],)).fetchone()
            assert doc.status=='ready' and doc.active_version_id==version.id and doc.visibility=='private'
            assert version.pdf_sha256==spec['sha256']
            found=db.execute('select * from pages where document_version_id=? order by page_index',(version.id,)).fetchall()
            assert [p.page_index for p in found]==list(range(spec['pages']))
            for p in found:
                f=db.execute('select * from page_features where page_id=?',(p.id,)).fetchone();assert f
                blob=(ROOT/f.tensor_path).read_bytes();assert sha(blob)==f.tensor_sha256
                saved=torch.load(ROOT/f.tensor_path,weights_only=True,map_location='cpu');tensor=saved['embeddings']
                assert tensor.dtype==torch.bfloat16 and tensor.shape==(1031,128) and saved['visual_patch_count']==1024
                export=(ROOT/f.export_path).read_bytes();assert sha(export)==f.export_sha256
                assert torch.equal(torch.tensor(json.loads(export),dtype=torch.float32),tensor.float())
                record=db.execute('select * from page_parses where task_id=? and page_id=?',(spec['task_id'],p.id)).fetchone();assert record.status in {'ready','no_candidates'}
                candidates=json.loads(record.candidates_json);assert sha(record.candidates_json.encode())==record.candidate_hash
                for c in candidates:
                    assert c['page_id']==p.id and c['page_number']==p.page_index+1 and c['render_sha256']==p.render_sha256
                    assert c['width_px']==p.width_px and c['height_px']==p.height_px
                    types[c['type']]+=1
                provenance=json.loads(record.provenance_json);receipt=read(ROOT/provenance['receipt_path'])
                assert sha((ROOT/provenance['receipt_path']).read_bytes())==provenance['receipt_sha256']
                assert sha((ROOT/provenance['raw_path']).read_bytes())==provenance['raw_sha256']
                assert receipt['network_attempts']==[] or receipt['network_attempts']==0
                assert not receipt['blocked_writes']
                runs=sum(s['forward_calls'] for s in receipt['sessions']);calls+=runs
                receipts.append({'page_id':p.id,'forward_calls':runs,'receipt':provenance['receipt_path'],'keys':list(receipt)})
                seconds+=receipt.get('parse_seconds',receipt.get('seconds',0))
                pages.append({'owner':spec['owner'],'page_id':p.id,'page_number':p.page_index+1,'shape':[1031,128],'dtype':'torch.bfloat16','patch_tokens':1024,'tensor_sha256':f.tensor_sha256,'export_sha256':f.export_sha256,'candidate_count':len(candidates),'candidate_hash':record.candidate_hash,'render_sha256':p.render_sha256,'size':[p.width_px,p.height_px]})
    audits={kind:[read(p) for p in (OUT/kind).glob('*.json')] for kind in ('page','query','region')}
    for kind,records in audits.items():assert all(r['network_attempts']==0 for r in records)
    report={'round':'R22','overall':'passed','new_complete_documents':2,'pages':pages,'candidate_types':dict(types),'candidate_count':sum(types.values()),'MinerU_ONNX_forward_calls':calls,'parser_receipts':receipts,'audit_counts':{k:len(v) for k,v in audits.items()},'workers':sorted({r['worker_pid'] for v in audits.values() for r in v}),'network_attempts':0,'limits':'Every stored full BF16 and exact float32 export rechecked. Counts include all saved actual calls, including repeated/cancelled browser requests; not accuracy or total process memory.'}
    save(ROOT/'docs/checks/stage2-6-artifacts.json',report)
    print(json.dumps({k:report[k] for k in ('overall','candidate_count','candidate_types','MinerU_ONNX_forward_calls','audit_counts','workers')}))


if __name__=='__main__':main()
