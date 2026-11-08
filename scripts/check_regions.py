"""R22 isolated real upload/parse/region acceptance setup; no formal credentials."""
import argparse
from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
import secrets
import sqlite3
import tarfile

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT,make_engine
from backend.db.models import User,AuthSession,LoginAttempt
from backend.db.seed import password_hasher,sha

OUT=ROOT/'runtime/verification/r22'
DATABASE=OUT/'metadata.sqlite3'
STATE=OUT/'state.json'
ORIGIN='http://127.0.0.1:3000'


def read(path):return json.loads(path.read_text('utf-8'))
def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def prepare():
    assert not DATABASE.exists()
    with closing(sqlite3.connect(OUT/'metadata-before.sqlite3')) as src,closing(sqlite3.connect(DATABASE)) as dst:src.backup(dst)
    engine=make_engine(DATABASE);passwords={name:secrets.token_urlsafe(24) for name in ('A','B','admin')}
    with Session(engine) as db,db.begin():
        db.query(AuthSession).delete();db.query(LoginAttempt).delete()
        for user in db.scalars(select(User)):
            user.password_hash=password_hasher.hash(passwords[user.username]);user.must_change_password=False;user.active=True;user.auth_version+=1
    engine.dispose()
    manifest=read(ROOT/'runtime/corpus/manifest.json')
    excluded={d['archive_member'] for d in manifest['documents']}
    for path in (ROOT/'runtime/verification/r15/real-attempt2/selected-pdfs.json',ROOT/'runtime/verification/r19/ui/selected-pdfs.json'):
        excluded.update(d['member'] for d in read(path))
    chosen=[]
    with tarfile.open(manifest['source_archive'],'r') as archive:
        for member in sorted((m for m in archive if m.isfile() and m.name.lower().endswith('.pdf') and m.name not in excluded),key=lambda m:m.name):
            data=archive.extractfile(member).read()
            try:count=len(PdfReader(BytesIO(data)).pages)
            except Exception:continue
            if 2<=count<=12:
                path=OUT/f'new-complete-{len(chosen)+1}.pdf';path.write_bytes(data)
                chosen.append({'owner':('A','B')[len(chosen)],'member':member.name,'path':str(path),'sha256':sha(data),'pages':count})
                if len(chosen)==2:break
    assert len(chosen)==2,'Not enough unselected complete PDFs; do not create synthetic substitute'
    write(STATE,{'passwords':passwords,'selected':chosen})
    write(OUT/'selected-pdfs.json',chosen)
    print(json.dumps({'new_complete_pdfs':[{k:v for k,v in d.items() if k!='path'} for d in chosen],'credentials':'random private runtime only'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare']);args=parser.parse_args();prepare()
