"""R21 authorized internal inference on real R19 uploads/R20 MinerU candidates."""
from contextlib import closing
import hashlib
import json
import os
import secrets
import sqlite3

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT,make_engine
from backend.db.models import AuthSession,Document,Page,PageParse,ParserProfile,ParsingTask,User
from backend.db.seed import password_hasher
from backend.parsing.adapter import load_profile
from backend.db.seed import canonical,sha
from backend.regions.service import prepare_request,rank_regions
from backend.search.worker import ModelWorker
from scripts.check_stage2_preflight import snapshot

OUT=ROOT/'runtime/verification/r21'
DATABASE=OUT/'metadata.sqlite3'


def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def main():
    assert (ROOT/'docs/checks/stage2-5-consistency.json').is_file()
    assert not DATABASE.exists()
    source=ROOT/'runtime/verification/r20/metadata.sqlite3'
    with closing(sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True)) as src,closing(sqlite3.connect(DATABASE)) as dst:src.backup(dst)
    engine=make_engine(DATABASE)
    # No historical test password or formal credentials are read or used.
    with Session(engine) as db,db.begin():
        db.query(AuthSession).delete()
        for user in db.scalars(select(User)):
            user.password_hash=password_hasher.hash(secrets.token_urlsafe(24));user.must_change_password=False
            user.active=True;user.auth_version+=1
    (OUT/'requests').mkdir();(OUT/'regions').mkdir()
    os.environ['LAYOUTPATCH_REGION_AUDIT_DIR']=str(OUT/'regions')
    worker=ModelWorker();results=[]
    try:
        with Session(engine) as db:
            profile=db.scalar(select(ParserProfile).where(ParserProfile.config_sha256==sha(canonical(load_profile()).encode())))
            targets=db.execute(select(ParsingTask,Document,User).join(Document,Document.active_version_id==ParsingTask.document_version_id)
                .join(User,User.id==Document.owner_id).where(ParsingTask.parser_profile_id==profile.id,ParsingTask.status=='ready',User.username.in_(['A','B']))
                .order_by(User.username)).all()
            assert len(targets)==2
            selected=[(t.id,d.id,u.id,u.username) for t,d,u in targets]
        encoder=sha((ROOT/'configs/colpali_local.json').read_bytes())
        for task_id,doc_id,user_id,name in selected:
            with Session(engine) as db:
                pages=list(db.scalars(select(Page).join(PageParse,PageParse.page_id==Page.id).where(PageParse.task_id==task_id,PageParse.status=='ready').order_by(Page.page_index)))
                page_ids=[p.id for p in pages]
            for number,page_id in enumerate(page_ids,1):
                question=f'What evidence is shown in the text, table or figure on this page? Verification R21 document {name}, page {number}.'
                with Session(engine) as db:
                    user=db.get(User,user_id)
                    request=prepare_request(db,user,page_id,task_id,encoder)
                    write(OUT/'requests'/f'{name}-{number}.json',request)
                    result=rank_regions(db,user,page_id,task_id,question,worker,encoder)
                    assert result['status']=='ready' and result['strict_load'] and not result['cache_hit']
                    assert result['query_sha256']==hashlib.sha256(question.encode()).hexdigest()
                    results.append({'owner':name,'page_number':number,'page_id':page_id,'result':result,'worker_audit':worker.last_audit})
        # A different new question reuses only P′; Q is encoded again in this worker.
        first=results[0]
        with Session(engine) as db:
            user=db.get(User,selected[0][2])
            reused=rank_regions(db,user,first['page_id'],selected[0][0],'Which candidate most directly supports the main statement on this page? R21 cache check.',worker,encoder)
            assert reused['cache_hit'] and reused['cache_key']==first['result']['cache_key']
            assert reused['d_forward_count']==len(results)
        assert len(results)==11 and sum(len(r['result']['rankings']) for r in results)==194
        report={'round':'R21','overall':'passed','scope':'R19 genuinely uploaded complete5/6-page PDFs with R20 real MinerU current profile; reused inputs, not new R21 uploads or unseen test set',
            'pages':results,'cache_reuse':reused,'query_forwards':worker.last_audit['forward_count'],'d_forwards':len(results),
            'candidate_count':194,'worker_pid':worker.last_audit['worker_pid'],'network_attempts':worker.last_audit['network_attempts'],
            'new_page_encoding_count':0,'new_parser_count':0,'database_unchanged_by_inference':None,
            'limits':'Real inference/input binding only; no region accuracy/gold/highlight/HTTP region evaluation.'}
        write(ROOT/'docs/checks/stage2-5-real.json',report)
        print(json.dumps({k:report[k] for k in ('query_forwards','d_forwards','candidate_count','worker_pid','network_attempts')}))
    finally:
        worker.close();engine.dispose()
        os.environ.pop('LAYOUTPATCH_REGION_AUDIT_DIR',None)


if __name__=='__main__':main()
