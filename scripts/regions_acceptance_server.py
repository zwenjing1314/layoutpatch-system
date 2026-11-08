"""R22 real isolated server; optional explicit browser delay/failure flags stay test-only."""
import os
import json
import time
from backend.search.qdrant import SearchUnavailable
from backend.auth.settings import AuthSettings
from backend.main import create_app
from scripts.check_regions import DATABASE,OUT

for kind in ('QUERY','PAGE','REGION'):
    os.environ[f'LAYOUTPATCH_{kind}_AUDIT_DIR']=str(OUT/kind.lower())
app=create_app(AuthSettings(database=DATABASE))

# Normal upload, parser and D calls remain the real implementations. Browser fault
# probes are explicitly file-gated, recorded separately, never imported by main.
real_rank=app.state.model_worker.rank_regions
def controlled_rank(*args,**kwargs):
    flag=OUT/'region-fault.json'
    if flag.exists():
        spec=json.loads(flag.read_text('utf-8'))
        with (OUT/'region-fault-events.jsonl').open('a',encoding='utf-8') as log:
            log.write(json.dumps({'event':'entered','mode':spec['mode'],'time':time.time()})+'\n')
        if spec['mode']=='failed':raise SearchUnavailable('Explicit R22 isolated failure fixture')
        if spec['mode']=='delay':time.sleep(6)
    result=real_rank(*args,**kwargs)
    return result
app.state.model_worker.rank_regions=controlled_rank

real_qdrant_request=app.state.qdrant.request
def audited_request(method,path,body=None,missing=False):
    result=real_qdrant_request(method,path,body,missing)
    if path.endswith('/points/query'):
        with (OUT/'qdrant-scope.jsonl').open('a',encoding='utf-8') as log:
            log.write(json.dumps({'method':method,'path':path,'body_without_query':{k:v for k,v in body.items() if k!='query'},
                'returned_ids':[p['id'] for p in result['points']],'time':time.time()})+'\n')
    return result
app.state.qdrant.request=audited_request
