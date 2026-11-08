"""R20 real parser acceptance in a fresh clone of uploaded ready PDFs; credentials stay private."""
import argparse
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.settings import AuthSettings
from backend.db.connection import ROOT, make_engine
from backend.db.models import AuthSession, Document, DocumentVersion, Job, Page, PageParse, ParserProfile, ParsingTask, User
from backend.db.seed import canonical, password_hasher, sha
from backend.main import create_app
from backend.parsing.runner import enqueue, ParsingRunner
from backend.parsing.adapter import load_profile
from backend.documents.pipeline import write_transaction
from scripts.check_stage2_preflight import snapshot
from scripts.migrate_database import migrate
from scripts.check_selection_http import dynamic_fingerprint

OUT = ROOT / "runtime/verification/r20"
STATE = OUT / "state.json"
DATABASE = OUT / "metadata.sqlite3"
ORIGIN = "http://127.0.0.1:3000"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path,value):
    with path.open("x",encoding="utf-8") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def prepare():
    source_path = ROOT / "runtime/verification/r19/ui/metadata.sqlite3"
    source_before = snapshot(source_path)
    with closing(sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro",uri=True)) as source, closing(sqlite3.connect(DATABASE)) as target:
        source.backup(target)
    migrate(DATABASE)
    engine = make_engine(DATABASE)
    passwords = {name:secrets.token_urlsafe(24) for name in ("A","B","admin")}
    with Session(engine) as db,db.begin():
        db.query(AuthSession).delete()
        for user in db.scalars(select(User)):
            user.password_hash=password_hasher.hash(passwords[user.username])
            user.must_change_password=False
            user.active=True
            user.auth_version+=1
        selected=[]
        for name in ("A","B"):
            user=db.scalar(select(User).where(User.username==name))
            doc=db.scalar(select(Document).join(DocumentVersion,DocumentVersion.id==Document.active_version_id)
                .join(Job,Job.document_version_id==DocumentVersion.id).where(Document.owner_id==user.id,Document.status=="ready",Job.status=="completed"))
            version=db.get(DocumentVersion,doc.active_version_id)
            selected.append({"owner":name,"document_id":doc.id,"version_id":version.id,"pdf_sha256":version.pdf_sha256,"pages":version.page_count})
    engine.dispose()
    write(STATE,{"database":str(DATABASE),"passwords":passwords,"selected":selected})
    write(OUT / "clone-baseline.json",{"r19_source":source_before,"clone":snapshot(DATABASE),"selection":selected,"selection_policy":"R19 genuinely uploaded complete5/6-page PDFs; no original13 reparsed, no gold or query passed to MinerU"})
    print("R20 isolated clone prepared; two real uploaded PDFs selected, random credentials private")


def real(owner):
    state=read(STATE)
    target=next(item for item in state["selected"] if item["owner"]==owner)
    engine=make_engine(DATABASE)
    with write_transaction(engine) as db:
        doc=db.get(Document,target["document_id"])
        previous=db.scalar(select(ParsingTask).where(ParsingTask.document_version_id==doc.active_version_id).order_by(ParsingTask.created_at.desc()).limit(1))
        matching = previous and db.get(ParserProfile,previous.parser_profile_id).config_sha256 == sha(canonical(load_profile()).encode())
        task=enqueue(db,doc,retry_task_id=previous.id if matching and previous.status in {"failed","partial","interrupted"} else None)
        task_id=task.id
    runner=ParsingRunner(engine)
    runner.run_one()
    with Session(engine) as db:
        task=db.get(ParsingTask,task_id)
        rows=db.execute(select(PageParse,Page).join(Page,Page.id==PageParse.page_id).where(PageParse.task_id==task_id).order_by(Page.page_index)).all()
        report={"date":datetime.now().astimezone().isoformat(),"owner":owner,"task_id":task_id,"status":task.status,"attempt":task.attempt,"error_code":task.error_code,"document":target,
                "pages":[{"page_id":page.id,"page_index":page.page_index,"status":record.status,"count":record.candidate_count,"candidate_hash":record.candidate_hash,"error_code":record.error_code,"types":sorted({c['type'] for c in json.loads(record.candidates_json or '[]')})} for record,page in rows]}
    engine.dispose()
    write(OUT / f"real-{owner}-{task_id}.json",report)
    print(json.dumps(report,ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("prepare","real"))
    parser.add_argument("owner",nargs="?",choices=("A","B"))
    args=parser.parse_args()
    prepare() if args.action=="prepare" else real(args.owner)
