"""Authorization/error contracts with real SQLite; model/Qdrant doubles explicitly scoped to these tests."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.auth.accounts import change_account
from backend.auth.settings import AuthSettings
from backend.db.connection import ROOT, make_engine
from backend.db.models import Document, DocumentVersion, Page, User, PipelineProfile, IndexGeneration, IndexPage
from backend.db.seed import seed
from backend.main import create_app
from backend.search.qdrant import Qdrant, SearchUnavailable
from backend.search.scope import allowed_scope
from backend.search.worker import SearchBusy
from backend.search.indexing import feature_digest, import_features, read_bundle
from scripts.migrate_database import migrate


class Encoder:
    def __init__(self): self.calls = 0; self.callback = None; self.error = None
    def encode(self, q, profile):
        self.calls += 1
        if self.callback: self.callback()
        if self.error: raise self.error
        return [[1.0] + [0.0]*127]
    def close(self): pass


class VectorStore:
    def __init__(self): self.calls = []; self.callback = None; self.error = None; self.mutate = None
    def query(self, scope, vector, k):
        self.calls.append(scope)
        if self.callback: self.callback()
        if self.error: raise self.error
        # Ranking double selects only from the supplied authorized scope.
        hits = [{"id": p.id, "score": float(100-i), "payload": {"page_id": p.id,
                 "document_id": p.document_id, "document_version_id": p.version_id,
                 "profile_id": scope.profile_id, "index_generation": scope.index_id,
                 "render_sha256": p.render_sha256, "embedding_sha256": p.embedding_sha256}}
                for i,p in enumerate(scope.pages[:k])]
        if self.mutate: self.mutate(hits)
        return hits


class SearchTests(unittest.TestCase):
    def setUp(self):
        directory = ROOT / "runtime/verification"
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="r10-test-", dir=directory)
        self.path = Path(self.temp.name)/"metadata.sqlite3"
        migrate(self.path)
        self.encoder, self.vectorstore = Encoder(), VectorStore()
        self.app = create_app(AuthSettings(database=self.path), model_worker=self.encoder, qdrant=self.vectorstore)
        self.engine = self.app.state.engine
        self.passwords = {name:secrets.token_urlsafe(24) for name in ("A","B","admin")}
        seed(self.engine, self.passwords.__getitem__)
        with Session(self.engine) as db, db.begin():
            db.execute(update(User).values(must_change_password=False))
            db.execute(update(Document).values(status="ready"))
            db.execute(update(PipelineProfile).values(status="validated"))
            index = db.scalar(select(IndexGeneration))
            index.status="ready"; index.page_count=13; index.vector_count=13*1031
            index.feature_file_sha256="a"*64; index.source_manifest_sha256="b"*64
            for page in db.scalars(select(Page)):
                db.add(IndexPage(index_id=index.id,page_id=page.id,embedding_sha256="c"*64,token_count=1031))
        self.client=TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.temp.cleanup()

    def login(self, name="A"):
        r=self.client.post('/auth/login',json={"username":name,"password":self.passwords[name]},headers={"Origin":"http://127.0.0.1:3000"})
        self.assertEqual(r.status_code,200)
        return r.json()

    def search(self, **kw): return self.client.get('/search',params={"q":"new question","k":3,**kw})
    def status(self,r,code):
        self.assertEqual(r.status_code,code)
        self.assertEqual(r.headers['cache-control'],'private, no-store')

    def test_auth_first_password_and_input_boundaries(self):
        self.status(self.search(),401)
        self.login()
        with self.engine.begin() as c: c.execute(update(User).where(User.username=='A').values(must_change_password=True))
        self.status(self.search(),403)
        with self.engine.begin() as c: c.execute(update(User).where(User.username=='A').values(must_change_password=False))
        for args in ({"q":"  "},{"q":"q"*2001},{"k":0},{"k":51},{"owner_id":"B"},{"scope":"all"},{"profile_id":"other"}):
            self.status(self.search(**args),422)
        self.status(self.client.get('/search?q=a&q=b'),422)
        self.assertEqual(self.encoder.calls,0)

    def test_private_scope_a_b_and_admin_empty_short_circuit(self):
        for user, count in (("A",5),("B",8)):
            self.login(user)
            r=self.search(k=50);self.status(r,200)
            self.assertEqual(len(r.json()['items']),count)
            with Session(self.engine) as db:
                owner=db.scalar(select(User).where(User.username==user)).id
            self.assertEqual({p.owner_id for p in self.vectorstore.calls[-1].pages},{owner})
        self.login('admin')
        calls=self.encoder.calls
        self.status(self.search(),200)
        self.assertEqual(self.search().json()['status'],'empty')
        self.assertEqual(self.encoder.calls,calls)
        self.assertEqual(len(self.vectorstore.calls),2)

    def test_shared_is_separate_admin_owned_document(self):
        with Session(self.engine) as db, db.begin():
            admin=db.scalar(select(User).where(User.username=='admin'))
            original=db.scalar(select(DocumentVersion)); p=db.scalar(select(Page))
            doc=Document(source_key='test-shared',owner_id=admin.id,display_name='Shared test',visibility='shared',status='ready')
            db.add(doc);db.flush()
            ver=DocumentVersion(document_id=doc.id,version=1,pdf_sha256=original.pdf_sha256,pdf_path=original.pdf_path,page_count=1,
                                render_profile_json=original.render_profile_json,render_profile_sha256=original.render_profile_sha256)
            db.add(ver);db.flush();doc.active_version_id=ver.id
            page=Page(document_version_id=ver.id,source_page_id='shared:p0',page_index=0,width_px=p.width_px,height_px=p.height_px,
                      render_sha256=p.render_sha256,image_path=p.image_path)
            db.add(page);db.flush(); index=db.scalar(select(IndexGeneration));index.page_count+=1;index.vector_count+=1031
            db.add(IndexPage(index_id=index.id,page_id=page.id,embedding_sha256='d'*64,token_count=1031))
            shared_id=doc.id
        for user, count in (('A',6),('B',9),('admin',1)):
            self.login(user);r=self.search(k=50);self.status(r,200);self.assertEqual(len(r.json()['items']),count)
        self.login('A')
        def revoke():
            with self.engine.begin() as c: c.execute(update(Document).where(Document.id==shared_id).values(visibility='private'))
        self.vectorstore.callback=revoke
        self.status(self.search(k=50),409)

    def test_revocation_and_scope_change_during_inference(self):
        self.login()
        self.encoder.callback=lambda: change_account(self.engine,'A','revoke',self.app.state.clock())
        self.status(self.search(),401)
        self.encoder.callback=None;self.login()
        def delete():
            with self.engine.begin() as c: c.execute(update(Document).where(Document.owner_id==select(User.id).where(User.username=='A').scalar_subquery()).values(status='deleted'))
        self.vectorstore.callback=delete
        self.status(self.search(),409)

    def test_dependency_failure_never_returns_empty_or_fallback(self):
        self.login()
        self.encoder.error=SearchUnavailable('test stopped model')
        self.status(self.search(),503);self.assertEqual(len(self.vectorstore.calls),0)
        self.encoder.error=SearchBusy('busy');self.status(self.search(),503)
        self.encoder.error=None;self.vectorstore.error=SearchUnavailable('qdrant down')
        self.status(self.search(),503)

    def test_untrusted_hits_and_nonfinite_scores_rejected(self):
        self.login()
        mutations=[lambda h:h[0].update(id='other-user-page'),lambda h:h[0].update(score=float('nan')),
                   lambda h:h[0]['payload'].update(profile_id='wrong'),lambda h:h.pop(),
                   lambda h:h.__setitem__(1,deepcopy(h[0]))]
        for mutation in mutations:
            self.vectorstore.mutate=mutation
            self.status(self.search(),503)

    def test_sql_failure_and_incomplete_index_fail_closed(self):
        self.login()
        with self.engine.begin() as c: c.exec_driver_sql('DELETE FROM index_pages')
        self.status(self.search(),503);self.assertEqual(self.encoder.calls,0)
        with self.engine.begin() as c: c.exec_driver_sql('DROP TABLE index_pages')
        self.status(self.search(),503)

    def test_qdrant_request_filters_before_topk_and_exact_no_prefetch(self):
        self.login()
        with Session(self.engine) as db:
            scope=allowed_scope(db,db.scalar(select(User).where(User.username=='A')))
        calls=[]
        q=Qdrant()
        with patch.object(q,'info',return_value={}), patch.object(q,'check_info'), patch.object(q,'request',side_effect=lambda m,p,b: calls.append(b) or {'points':[]}):
            q.query(scope,[[1.0]+[0.0]*127],3)
        body=calls[0]
        self.assertEqual(body['params'],{'exact':True});self.assertNotIn('prefetch',body)
        clauses=body['filter']['must']
        self.assertEqual(clauses[0]['match']['any'],sorted({p.version_id for p in scope.pages}))
        self.assertEqual(clauses[1]['match']['value'],scope.profile_id)
        self.assertEqual(clauses[2]['match']['value'],scope.index_id)
        self.assertEqual(set(clauses[3]['has_id']),{p.id for p in scope.pages})

    def test_each_query_invokes_encoder_again(self):
        self.login()
        for q in ('first unseen question','second unseen question','first unseen question'):
            self.status(self.search(q=q),200)
        self.assertEqual(self.encoder.calls,3)

    def test_active_index_missing_remote_is_not_recreated(self):
        self.login()
        q=Qdrant()
        with patch.object(q,'info',return_value=None),patch.object(q,'create') as create:
            with self.assertRaises(SearchUnavailable):
                import_features(self.engine,ROOT/'runtime/indexes/r10-features/manifest.json',q)
            create.assert_not_called()
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(IndexGeneration)).status,'ready')


class FeatureIntegrityTests(unittest.TestCase):
    def test_float32_roundtrip_uses_bytes_not_python_double_equality(self):
        original=[[0.10009765625]+[0.0]*127]
        serialized=[[0.100097656]+[0.0]*127]
        self.assertNotEqual(original,serialized)
        self.assertEqual(feature_digest(original),feature_digest(serialized))
        serialized[0][0]=0.1231
        self.assertNotEqual(feature_digest(original),feature_digest(serialized))

    def test_changed_feature_manifest_rejected_before_network(self):
        with tempfile.TemporaryDirectory(prefix='r10-invalid-',dir=ROOT/'runtime/verification') as temp:
            path=Path(temp)/'manifest.json'
            data=json.loads((ROOT/'runtime/indexes/r10-features/manifest.json').read_text())
            data['source']['files']['page_embeddings.pt']='0'*64
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'identity mismatch'):read_bundle(path)

    def test_qdrant_wrong_metric_quantization_or_count_rejected(self):
        info={'config':{'params':{'vectors':{'original':{'size':128,'distance':'Dot','datatype':'float32',
              'multivector_config':{'comparator':'max_sim'},'hnsw_config':{'m':0}}}}},'points_count':13}
        Qdrant.check_info(info,13)
        for mode in ('metric','quantization','count'):
            wrong=deepcopy(info)
            if mode=='metric':wrong['config']['params']['vectors']['original']['distance']='Cosine'
            if mode=='quantization':wrong['config']['quantization_config']={'scalar':{}}
            if mode=='count':wrong['points_count']=12
            with self.assertRaises(SearchUnavailable):Qdrant.check_info(wrong,13)


if __name__=='__main__': unittest.main(verbosity=2)
