"""Back up the formal development DB, migrate, import, and check preserved data."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import uuid

from backend.db.connection import ROOT, DEFAULT_DATABASE, make_engine
from backend.search.indexing import import_features
from scripts.migrate_database import migrate


def snapshot(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row
        return {name:[dict(row) for row in c.execute('SELECT * FROM '+name+' ORDER BY id')]
                for name in ('users','documents','document_versions','pages','pipeline_profiles','index_generations')}


def main():
    folder=ROOT/'runtime/verification/r10'/('formal-'+uuid.uuid4().hex[:12])
    folder.mkdir(parents=True)
    backup=folder/'metadata-before-0003.sqlite3'
    with closing(sqlite3.connect(DEFAULT_DATABASE.as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(backup)) as dst:
        src.backup(dst)
    before=snapshot(backup)
    migrate();migrate()
    engine=make_engine()
    try:
        first=import_features(engine,ROOT/'runtime/indexes/r10-features/manifest.json')
        after_first=snapshot(DEFAULT_DATABASE)
        second=import_features(engine,ROOT/'runtime/indexes/r10-features/manifest.json')
        after=snapshot(DEFAULT_DATABASE)
    finally:
        engine.dispose()
    unchanged={name:before[name]==after[name] for name in ('users','document_versions','pages')}
    for name,allowed in {'documents':{'status'},'pipeline_profiles':{'status'},
                         'index_generations':{'status','page_count','vector_count','feature_file_sha256','source_manifest_sha256'}}.items():
        clean=lambda rows:[{k:v for k,v in row.items() if k not in allowed} for row in rows]
        unchanged[name+'_other_fields']=clean(before[name])==clean(after[name])
    if not all(unchanged.values()) or after_first!=after:raise AssertionError('Unexpected formal data change')
    with closing(sqlite3.connect(DEFAULT_DATABASE.as_uri()+'?mode=ro',uri=True)) as c:
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
        fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
        memberships=c.execute('SELECT count(*) FROM index_pages').fetchone()[0]
        revision=c.execute('SELECT version_num FROM alembic_version').fetchone()[0]
    if integrity!='ok' or fk or memberships!=13:raise AssertionError('Formal integrity failed')
    report={'date':'2026-11-07','round':'R10','revision':revision,'backup':backup.relative_to(ROOT).as_posix(),
            'preserved_data':unchanged,'repeated_migration':True,'repeat_import_logically_unchanged':after_first==after,
            'repeat_import_no_upsert':second['existing_collection_verified_without_upsert'],
            'integrity':integrity,'foreign_key_violations':fk,'index_memberships':memberships,'index':first,
            'account_password_changes':False,'overall':'passed'}
    (ROOT/'docs/checks/stage1b-4-formal.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
