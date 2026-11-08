"""R20 explicit geometry/failure fixtures, separate from real uploaded-PDF acceptance."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
from uuid import uuid4

from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT, make_engine
from backend.db.models import Document, DocumentVersion, Page, PageParse, ParsingTask, User
from backend.db.seed import canonical, sha
from backend.documents.pipeline import write_transaction
from backend.parsing.adapter import load_profile, parse_page, run_child, verify_resources
from backend.parsing.candidates import ParseError
from backend.parsing.runner import enqueue, ParsingRunner, recover
from scripts.check_parsing import OUT, DATABASE, read, write
import subprocess


def main():
    destination=OUT / "faults-final.sqlite3"
    if destination.exists():raise RuntimeError('Preserve existing fault evidence; use a new attempt path')
    with closing(sqlite3.connect(DATABASE)) as source,closing(sqlite3.connect(destination)) as target:source.backup(target)
    engine=make_engine(destination)
    recover(engine)  # A live-source clone may contain in-progress metadata; it is not a live worker.
    checks=[]
    def check(name,condition,**details):
        checks.append({"name":name,"passed":bool(condition),**details})
        if not condition:raise AssertionError(name)
    # Validate actual local resources once. The parser itself remains the real worker.
    profile=load_profile();verify_resources(profile)
    base=OUT / "geometry-fixtures-final";base.mkdir(exist_ok=False)
    with Session(engine) as db:
        user=db.scalar(select(User).where(User.username=='A'))
        owner_id=user.id
    ids={}
    for name,width,height,rotate,crop in (
        ('blank-portrait',301.25,499.75,0,False),('blank-landscape',499.75,301.25,0,False),
        ('rotated',301.25,499.75,90,False),('cropped',301.25,499.75,0,True)):
        writer=PdfWriter();p=writer.add_blank_page(width=width,height=height)
        if rotate:p.rotate(rotate)
        if crop:p.cropbox.lower_left=(10,20);p.cropbox.upper_right=(width-10,height-20)
        source=base / (name+'.pdf')
        with source.open('xb') as stream:writer.write(stream)
        pdf_sha=sha(source.read_bytes())
        rendered=ROOT / 'runtime/corpus/ingest' / ('r20-geometry-'+str(uuid4()))
        result=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-B',str(ROOT/'scripts/render_upload.py'),str(source),str(rendered),pdf_sha,'1'],capture_output=True,timeout=60)
        check(name+'_rendered_by_frozen_renderer',result.returncode==0)
        manifest=read(rendered/'render-manifest.json');entry=manifest['pages'][0]
        with write_transaction(engine) as db:
            doc=Document(source_key='r20-fixture:'+name,owner_id=owner_id,display_name=name+'.pdf',status='registered')
            db.add(doc);db.flush()
            version=DocumentVersion(document_id=doc.id,version=1,pdf_sha256=pdf_sha,pdf_path=source.relative_to(ROOT).as_posix(),page_count=1,
                render_profile_json=canonical(manifest['render_profile']),render_profile_sha256=sha(canonical(manifest['render_profile']).encode()))
            db.add(version);db.flush()
            db.add(Page(document_version_id=version.id,source_page_id='r20-fixture:'+name,page_index=0,**{k:entry[k] for k in ('width_px','height_px','render_sha256','image_path')}))
            db.flush();doc.active_version_id=version.id;doc.status='ready'
            task=enqueue(db,doc);ids[name]={'document_id':doc.id,'task_id':task.id}
    runner=ParsingRunner(engine,verifier=lambda config:None) # resources actually checked above; no fake parser
    for _ in range(4):runner.run_one()
    with Session(engine) as db:
        for name,identity in ids.items():
            record=db.scalar(select(PageParse).where(PageParse.task_id==identity['task_id']))
            if name.startswith('blank'):
                check(name+'_real_mineru_no_candidates',record.status=='no_candidates' and record.candidate_count==0 and json.loads(record.candidates_json)==[],status=record.status,error=record.error_code)
            else:
                check(name+'_explicit_geometry_refusal',record.status=='failed' and record.error_code=='UNSUPPORTED_PDF_GEOMETRY',status=record.status,error=record.error_code)
            check(name+'_document_still_ready',db.get(Document,identity['document_id']).status=='ready')
    # Real subprocess timeout, forced before MinerU can finish; not a natural timing claim.
    def copy_fixture(db,source_name,name):
        original=db.get(Document,ids[source_name]['document_id'])
        old=db.get(DocumentVersion,original.active_version_id)
        old_page=db.scalar(select(Page).where(Page.document_version_id==old.id))
        doc=Document(source_key='r20-fixture:'+name,owner_id=owner_id,display_name=name+'.pdf',status='registered')
        db.add(doc);db.flush()
        version=DocumentVersion(document_id=doc.id,version=1,**{key:getattr(old,key) for key in ('pdf_sha256','pdf_path','page_count','render_profile_json','render_profile_sha256')})
        db.add(version);db.flush()
        db.add(Page(document_version_id=version.id,source_page_id='r20-fixture:'+name,page_index=0,
            **{key:getattr(old_page,key) for key in ('width_px','height_px','render_sha256','image_path')}))
        db.flush();doc.active_version_id=version.id;doc.status='ready'
        return doc,version
    with write_transaction(engine) as db:
        doc,_=copy_fixture(db,'blank-portrait','timeout')
        task=enqueue(db,doc);timeout_id=task.id
    def deadline_child(python,script,request_path,timeout,log_name):
        return run_child(python,script,request_path,.25 if 'mineru' in script else timeout,log_name)
    with patch('backend.parsing.adapter.run_child',side_effect=deadline_child):
        ParsingRunner(engine,verifier=lambda c:None).run_one()
    with Session(engine) as db:
        record=db.scalar(select(PageParse).where(PageParse.task_id==timeout_id))
        check('real_worker_deadline_persisted',record.status=='timeout' and record.error_code=='PARSER_TIMEOUT',injection='0.25s child timeout',task_id=timeout_id)
    # Actual invalid parser input exception: corrupt a PRIVATE fixture copy, never source PDFs.
    with write_transaction(engine) as db:
        doc,version=copy_fixture(db,'blank-landscape','invalid')
        task=enqueue(db,doc);bad_id=task.id
        bad=base/'corrupt-explicit.pdf';bad.write_bytes(b'%PDF-explicit-invalid-fixture')
        version.pdf_path=bad.relative_to(ROOT).as_posix();version.pdf_sha256=sha(bad.read_bytes())
    ParsingRunner(engine,verifier=lambda c:None).run_one()
    with Session(engine) as db:
        record=db.scalar(select(PageParse).where(PageParse.task_id==bad_id))
        check('real_invalid_pdf_exception_persisted',record.status=='failed' and record.error_code=='RENDER_IDENTITY_MISMATCH',task_id=bad_id)
        check('invalid_pdf_did_not_revoke_page_readiness',db.get(Document,ids['blank-landscape']['document_id']).status=='ready')
    engine.dispose()
    write(ROOT/'docs/checks/stage2-4-faults.json',{'round':'R20','overall':'passed','checks':checks,'fixture_scope':'Blank/rotated/cropped PDFs are explicit generated geometry fixtures, unindexed. No fake retrieval or manually specified candidate boxes. Timeout0.25s and corrupt PDF are explicit fault injections.'})
    print(f'{len(checks)} geometry/real-process failure checks passed')


if __name__=='__main__':main()
