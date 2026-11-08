"""Internal authorization/error tests; worker is an explicit double, not D evidence."""
from copy import deepcopy
import unittest

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Document,Page,PageFeature,PageParse,ParserProfile,ParsingTask,User
from backend.db.seed import canonical,sha
from backend.parsing.candidates import ParseError
from backend.regions.service import prepare_request,rank_regions
from tests import test_search as fixture_source


class WorkerDouble:
    def __init__(self):self.calls=0;self.callback=None;self.mutate=None
    def rank_regions(self,question,request,encoder):
        self.calls+=1
        if self.callback:self.callback()
        result={'query_sha256':sha(question.encode()),'regions':{'status':'ready','rankings':[{'candidate_id':c['candidate_id'],'layout_id':c['layout_id'],'rank':i+1,'score':1.0} for i,c in enumerate(request['candidates'])]}}
        if self.mutate:self.mutate(result)
        return result


class Regions(unittest.TestCase):
    setUpFixture=fixture_source.SearchTests.setUp
    tearDown=fixture_source.SearchTests.tearDown

    def setUp(self):
        self.setUpFixture();self.worker=WorkerDouble()
        self.encoder=sha((__import__('backend.db.connection',fromlist=['ROOT']).ROOT/'configs/colpali_local.json').read_bytes())
        with Session(self.engine) as db,db.begin():
            self.user_id=db.scalar(select(User.id).where(User.username=='A'))
            doc=db.scalar(select(Document).where(Document.owner_id==self.user_id));self.doc_id=doc.id
            page=db.scalar(select(Page).where(Page.document_version_id==doc.active_version_id));self.page_id=page.id
            profile=ParserProfile(config_json='{}',config_sha256=sha(b'{}'));db.add(profile);db.flush()
            task=ParsingTask(document_version_id=doc.active_version_id,parser_profile_id=profile.id,status='ready',attempt=1)
            db.add(task);db.flush();self.task_id=task.id
            c={'document_id':doc.id,'document_version_id':doc.active_version_id,'page_id':page.id,'page_index':page.page_index,'page_number':page.page_index+1,
                'render_sha256':page.render_sha256,'width_px':page.width_px,'height_px':page.height_px,'parser_profile_sha256':profile.config_sha256,
                'bbox':[0,0,10,10],'layout_id':0,'candidate_id':page.id+':block:0','type':'text','coordinate_system':'original_png_pixel_xyxy_top_left'}
            raw=canonical([c]);db.add(PageParse(task_id=task.id,page_id=page.id,status='ready',candidate_count=1,candidates_json=raw,candidate_hash=sha(raw.encode()),
                render_sha256=page.render_sha256,width_px=page.width_px,height_px=page.height_px))
            db.add(PageFeature(page_id=page.id,encoder_sha256=self.encoder,tensor_path='explicit-test-double.pt',tensor_sha256='a'*64,export_path='explicit-test-double.json',export_sha256='b'*64))

    def rank(self,name='A'):
        with Session(self.engine) as db:
            return rank_regions(db,db.scalar(select(User).where(User.username==name)),self.page_id,self.task_id,'new question',self.worker,self.encoder)

    def change(self,model,key,**values):
        with Session(self.engine) as db,db.begin():
            row=db.get(model,key)
            for k,v in values.items():setattr(row,k,v)

    def test_owner_and_no_admin_private_bypass(self):
        self.assertEqual(self.rank()['status'],'ready')
        for name in ('B','admin'):
            with self.assertRaises(HTTPException) as error:self.rank(name)
            self.assertEqual(error.exception.status_code,404)
        self.assertEqual(self.worker.calls,1)

    def test_missing_or_wrong_full_feature_rejected_before_worker(self):
        self.change(PageFeature,self.page_id,encoder_sha256='d'*64)
        with self.assertRaises(ParseError):self.rank()
        self.assertEqual(self.worker.calls,0)

    def test_candidate_set_corruption_rejected_before_worker(self):
        self.change(PageParse,(self.task_id,self.page_id),candidate_hash='d'*64)
        with self.assertRaises(ParseError):self.rank()
        self.assertEqual(self.worker.calls,0)

    def test_revocation_after_forward_rechecks_current_database(self):
        self.worker.callback=lambda:self.change(Document,self.doc_id,status='deleted')
        with self.assertRaises(HTTPException) as error:self.rank()
        self.assertEqual(error.exception.status_code,404)
        self.assertEqual(self.worker.calls,1)

    def test_auth_version_change_during_forward_is_rejected(self):
        self.worker.callback=lambda:self.change(User,self.user_id,auth_version=99)
        with self.assertRaises(ParseError):self.rank()

    def test_candidate_change_during_forward_is_rejected(self):
        self.worker.callback=lambda:self.change(PageParse,(self.task_id,self.page_id),candidate_hash='d'*64)
        with self.assertRaises(ParseError):self.rank()

    def test_inactive_or_first_password_principal_is_rejected(self):
        self.change(User,self.user_id,must_change_password=True)
        with self.assertRaises(HTTPException):self.rank()
        self.assertEqual(self.worker.calls,0)

    def test_nonfinite_duplicate_or_wrong_result_ids_are_rejected(self):
        for mutate in (lambda r:r['regions']['rankings'][0].update(score=float('nan')),
                lambda r:r['regions']['rankings'][0].update(candidate_id='other'),
                lambda r:r['regions']['rankings'].append(deepcopy(r['regions']['rankings'][0]))):
            self.worker.mutate=mutate
            with self.assertRaises(ParseError):self.rank()


if __name__=='__main__':unittest.main()
