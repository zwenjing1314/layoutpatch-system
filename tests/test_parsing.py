"""Strict coordinate and persistent parser contracts. All parser doubles are explicit here."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Document, Page, PageParse, ParsingTask, User
from backend.documents.pipeline import write_transaction
from backend.parsing.candidates import ParseError, export_candidates
from backend.parsing.runner import ParsingRunner, recover
from backend.parsing.store import read_candidates
from backend.db.seed import canonical,sha
from tests import test_search as source

ORIGIN="http://127.0.0.1:3000"


class Coordinates(unittest.TestCase):
    def setUp(self):
        self.identity={"page_id":"p","page_index":3,"width_px":1203,"height_px":1601,"render_sha256":"a"*64}
        self.geometry={"page_size_points":[601.2,800.5],"rotation":0,"cropbox":[0,0,601.2,800.5],"mediabox":[0,0,601.2,800.5],
            "parser_points_to_png":[2,0,0,2,0,0],"width_px":1203,"height_px":1601,"render_sha256":"a"*64}
        self.payload={"schema":"docvortex.middle","schema_version":"2.0","pages":[{"page_idx":3,"blocks":[{"index":7,"type":"table","bbox":[.1,.2,.8,.9]}]}],
            "extensions":{"docvortex_layout":{"version":1,"pages":[{"page_idx":3,"width_pt":601.2,"height_pt":800.5}]}}}

    def export(self):
        return export_candidates(self.payload,self.identity,self.geometry)

    def test_fractional_pdf_scale_not_rounded_png_or_448(self):
        item=self.export()[0]
        self.assertEqual(item['candidate_id'],'p:block:7')
        self.assertEqual(item['bbox'],[120.24000000000001,320.20000000000005,961.9200000000001,1440.9])
        self.assertEqual(item['coordinate_system'],'original_png_pixel_xyxy_top_left')

    def test_empty_page_is_legitimate(self):
        self.payload['pages'][0]['blocks']=[]
        self.assertEqual(self.export(),[])
        del self.payload['pages'][0]['blocks']
        self.assertEqual(self.export(),[])
        self.payload['pages'][0]['blocks']=None
        with self.assertRaises(ParseError):self.export()

    def test_invalid_nonfinite_boolean_reversed_and_outside_boxes_fail(self):
        for box in ([0,0,0,1],[0,0,1,float('nan')],[0,False,1,1],[-.001,0,1,1],[0,0,1.00001,1],[1,0,.5,1]):
            with self.subTest(box=box),self.assertRaises(ParseError):
                self.payload['pages'][0]['blocks'][0]['bbox']=box
                self.export()

    def test_unknown_type_duplicate_id_and_wrong_page_fail(self):
        for mutate in (
            lambda p:p['pages'][0]['blocks'][0].update(type='unmapped'),
            lambda p:p['pages'][0]['blocks'].append(deepcopy(p['pages'][0]['blocks'][0])),
            lambda p:p['pages'][0].update(page_idx=0),
            lambda p:p['extensions']['docvortex_layout']['pages'][0].update(width_pt=400)):
            original=deepcopy(self.payload)
            mutate(self.payload)
            with self.assertRaises(ParseError):self.export()
            self.payload=original

    def test_duplicate_boxes_keep_distinct_ids(self):
        other=deepcopy(self.payload['pages'][0]['blocks'][0]);other['index']=8
        self.payload['pages'][0]['blocks'].append(other)
        self.assertEqual(len(self.export()),2)

    def test_rotation_crop_origin_and_render_hash_rejected(self):
        for values in ({'rotation':90},{'cropbox':[10,0,601.2,800.5]},{'mediabox':[1,0,601.2,800.5]}, {'render_sha256':'b'*64}):
            original=deepcopy(self.geometry);self.geometry.update(values)
            with self.assertRaises(ParseError):self.export()
            self.geometry=original


class ParsingContracts(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ,{"LAYOUTPATCH_PARSE_ENABLED":"false"}):
            source.SearchTests.setUp(self)
        self.login()
        with Session(self.engine) as db:
            user=db.scalar(select(User).where(User.username=='A'))
            self.document=db.scalar(select(Document).where(Document.owner_id==user.id)).id
        self.url=f"/documents/{self.document}/parsing"
        self.csrf=self.client.get('/auth/me').json()['csrf_token']

    tearDown=source.SearchTests.tearDown
    login=source.SearchTests.login
    search=source.SearchTests.search
    status=source.SearchTests.status

    def post(self,body=None,**kw):
        return self.client.post(self.url,json=body or {},headers=kw.get('headers',{'Origin':ORIGIN,'X-CSRF-Token':self.csrf}))

    def requested(self):
        response=self.post();self.status(response,202)
        return response.json()

    def runner(self,parser):
        return ParsingRunner(self.engine,parser=parser,verifier=lambda profile:None)

    def test_origin_csrf_owner_first_change_and_no_private_payload(self):
        self.status(self.post(headers={'Origin':'https://bad.invalid','X-CSRF-Token':self.csrf}),403)
        self.status(self.post(headers={'Origin':ORIGIN}),403)
        self.status(self.post({'owner_id':'B'}),422)
        self.status(self.client.get(self.url),200)
        data=self.requested()
        self.assertNotIn('candidates_json',str(data));self.assertNotIn('pdf_path',str(data))
        for name in ('B','admin'):
            self.login(name)
            self.csrf=self.client.get('/auth/me').json()['csrf_token']
            self.status(self.client.get(self.url),404);self.status(self.post(),404)
        self.client.cookies.clear();self.status(self.client.get(self.url),401)
        self.login()
        with Session(self.engine) as db,db.begin():
            db.scalar(select(User).where(User.username=='A')).must_change_password=True
        self.status(self.client.get(self.url),403)

    def test_pending_document_cannot_parse(self):
        with Session(self.engine) as db,db.begin():db.get(Document,self.document).status='registered'
        self.status(self.post(),409)

    def test_concurrent_request_is_idempotent(self):
        with ThreadPoolExecutor(3) as pool:
            results=list(pool.map(lambda _:self.post(),range(3)))
        self.assertTrue(all(r.status_code==202 for r in results))
        self.assertEqual(len({r.json()['task_id'] for r in results}),1)
        with Session(self.engine) as db:self.assertEqual(len(list(db.scalars(select(ParsingTask)))),1)

    def test_no_candidates_persist_without_changing_search_or_image(self):
        task=self.requested()
        self.runner(lambda *args:([],{'explicit_test_double':True})).run_one()
        current=self.client.get(self.url).json()
        self.assertEqual(current['status'],'ready')
        self.assertTrue(all(p['status']=='no_candidates' and p['candidate_count']==0 and p['candidate_hash'] for p in current['pages']))
        self.assertEqual(self.requested()['task_id'],task['task_id'])
        hit=self.search().json()['items'][0]
        self.status(self.client.get(hit['preview_url']),200)

    def test_timeout_error_and_retry_preserve_attempts(self):
        task=self.requested();count=0
        def parser(*args):
            nonlocal count
            count+=1
            if count==1:raise ParseError('PARSER_TIMEOUT')
            if count==2:raise ValueError('private diagnostic never in response')
            return [],{'explicit_test_double':True}
        self.runner(parser).run_one()
        current=self.client.get(self.url).json()
        self.assertEqual(current['status'],'partial')
        self.assertEqual([p['status'] for p in current['pages']][:2],['timeout','failed'])
        self.assertNotIn('private diagnostic',str(current))
        self.status(self.post({'retry_task_id':'00000000-0000-4000-8000-000000000000'}),409)
        retry=self.post({'retry_task_id':task['task_id']});self.status(retry,202)
        self.assertEqual(retry.json()['attempt'],2)
        self.status(self.post({'retry_task_id':task['task_id']}),409)
        self.runner(lambda *args:([],{})).run_one()
        with Session(self.engine) as db:
            self.assertEqual(db.get(ParsingTask,task['task_id']).status,'partial')
            self.assertEqual(len(list(db.scalars(select(ParsingTask)))),2)

    def test_restart_marks_running_only_and_preserves_ready_page(self):
        task=self.requested()
        with write_transaction(self.engine) as db:
            db.get(ParsingTask,task['task_id']).status='running'
            pages=list(db.scalars(select(PageParse).where(PageParse.task_id==task['task_id'])))
            pages[0].status='no_candidates';pages[0].candidates_json='[]';pages[0].candidate_hash='a'*64
            pages[1].status='running'
        recover(self.engine)
        current=self.client.get(self.url).json()
        self.assertEqual(current['status'],'interrupted')
        self.assertEqual(sorted(p['status'] for p in current['pages']),['interrupted']*4+['no_candidates'])
        recover(self.engine)
        self.assertEqual(self.client.get(self.url).json(),current)

    def test_withdrawal_during_parser_does_not_publish_candidates(self):
        task=self.requested()
        def parser(*args):
            with Session(self.engine) as db,db.begin():db.get(Document,self.document).status='deleted'
            return [],{}
        self.runner(parser).run_one()
        self.status(self.client.get(self.url),404)
        with Session(self.engine) as db:
            self.assertEqual(db.get(ParsingTask,task['task_id']).error_code,'PARSER_AUTHORITY_CHANGED')
            self.assertTrue(all(p.candidates_json is None for p in db.scalars(select(PageParse))))

    def test_resource_failure_has_no_effect_on_page_ready(self):
        task=self.requested()
        def verify(profile):raise ParseError('PARSER_RESOURCE_IDENTITY_MISMATCH')
        ParsingRunner(self.engine,verifier=verify).run_one()
        self.assertEqual(self.client.get(self.url).json()['status'],'failed')
        self.status(self.search(),200)
        hit=self.search().json()['items'][0];self.status(self.client.get(hit['preview_url']),200)
        with Session(self.engine) as db:self.assertEqual(db.get(Document,self.document).status,'ready')

    def test_shared_status_read_only_and_rechecks_owner_enabled(self):
        self.requested()
        with Session(self.engine) as db,db.begin():
            doc=db.get(Document,self.document);admin=db.scalar(select(User).where(User.username=='admin'))
            doc.owner_id=admin.id;doc.visibility='shared'
        self.login('B');self.csrf=self.client.get('/auth/me').json()['csrf_token']
        self.status(self.client.get(self.url),200);self.status(self.post(),404)
        with Session(self.engine) as db,db.begin():db.scalar(select(User).where(User.username=='admin')).active=False
        self.status(self.client.get(self.url),404)

    def test_candidate_reader_reauthorizes_and_rejects_corruption(self):
        task=self.requested()
        def parser(task_id,version,page,config):
            return [{"document_id":version.document_id,"document_version_id":version.id,"page_id":page.id,"page_index":page.page_index,
                "page_number":page.page_index+1,"width_px":page.width_px,"height_px":page.height_px,"render_sha256":page.render_sha256,
                "parser_profile_sha256":sha(canonical(config).encode()),"candidate_id":page.id+':block:0',"layout_id":0,"bbox":[0,0,10,10],
                "coordinate_system":"original_png_pixel_xyxy_top_left","type":"text"}],{'explicit_test_double':True}
        self.runner(parser).run_one()
        page_id=self.client.get(self.url).json()['pages'][0]['page_id']
        with Session(self.engine) as db:
            a=db.scalar(select(User).where(User.username=='A'))
            candidates,identity=read_candidates(db,a,page_id,task['task_id'])
            self.assertEqual(len(candidates),1);self.assertTrue(identity['candidate_hash'])
            b=db.scalar(select(User).where(User.username=='B'))
            from fastapi import HTTPException
            with self.assertRaises(HTTPException):read_candidates(db,b,page_id,task['task_id'])
        with Session(self.engine) as db,db.begin():db.get(PageParse,(task['task_id'],page_id)).candidates_json='[]'
        with Session(self.engine) as db:
            a=db.scalar(select(User).where(User.username=='A'))
            with self.assertRaises(ParseError):read_candidates(db,a,page_id,task['task_id'])

    def test_version_identity_change_during_parse_is_not_published(self):
        from backend.db.models import DocumentVersion
        task=self.requested()
        def parser(task_id,version,page,config):
            with Session(self.engine) as db,db.begin():db.get(DocumentVersion,version.id).pdf_sha256='f'*64
            return [],{}
        self.runner(parser).run_one()
        self.assertEqual(self.client.get(self.url).json()['error_code'],'PARSER_INPUT_CHANGED')
        with Session(self.engine) as db:self.assertTrue(all(p.candidates_json is None for p in db.scalars(select(PageParse))))
