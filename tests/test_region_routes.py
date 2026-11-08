"""Real SQLite/cookie/PNG boundary tests; inference double explicitly identified."""
from io import BytesIO
import json
import unittest

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT
from backend.db.models import Document,Page,PageFeature,PageParse,ParserProfile,ParsingTask,User,AuthSession
from backend.db.seed import canonical,sha
from backend.parsing.adapter import load_profile
from backend.search.qdrant import SearchUnavailable
from tests import test_search as fixture

ORIGIN='http://127.0.0.1:3000'


class RegionWorker:
    def __init__(self):self.calls=0;self.callback=None;self.failure=False;self.corrupt=None
    def rank_regions(self,q,inputs,encoder):
        self.calls+=1
        if self.callback:self.callback()
        if self.failure:raise SearchUnavailable('explicit test double failure')
        result={'query_sha256':sha(q.encode()),'regions':{'status':'ready','d_profile_sha256':sha((ROOT/'configs/d_no_text_local.json').read_bytes()),
            'rankings':[{'candidate_id':c['candidate_id'],'layout_id':c['layout_id'],'rank':i+1,'score':1.0} for i,c in enumerate(inputs['candidates'])]}}
        if self.corrupt:self.corrupt(result)
        return result


class RegionRoutes(unittest.TestCase):
    tearDown=fixture.SearchTests.tearDown
    login=fixture.SearchTests.login

    def setUp(self):
        fixture.SearchTests.setUp(self);self.login()
        self.region_worker=RegionWorker();self.encoder.rank_regions=self.region_worker.rank_regions
        self.csrf=self.client.get('/auth/me').json()['csrf_token']
        self.headers={'Origin':ORIGIN,'X-CSRF-Token':self.csrf}
        with Session(self.engine) as db,db.begin():
            self.owner=db.scalar(select(User.id).where(User.username=='A'))
            doc=db.scalar(select(Document).where(Document.owner_id==self.owner));self.doc=doc.id
            page=db.scalar(select(Page).where(Page.document_version_id==doc.active_version_id));self.page=page.id
            profile=ParserProfile(config_json=canonical(load_profile()),config_sha256=sha(canonical(load_profile()).encode()))
            db.add(profile);db.flush()
            task=ParsingTask(document_version_id=doc.active_version_id,parser_profile_id=profile.id,status='ready',attempt=1);db.add(task);db.flush();self.task=task.id
            c={'document_id':doc.id,'document_version_id':doc.active_version_id,'page_id':page.id,'page_index':page.page_index,'page_number':page.page_index+1,
                'render_sha256':page.render_sha256,'width_px':page.width_px,'height_px':page.height_px,'parser_profile_sha256':profile.config_sha256,
                'bbox':[1.2,2.3,15.6,20.7],'layout_id':3,'candidate_id':page.id+':block:3','type':'table','coordinate_system':'original_png_pixel_xyxy_top_left'}
            raw=canonical([c]);db.add(PageParse(task_id=task.id,page_id=page.id,status='ready',candidate_count=1,candidates_json=raw,candidate_hash=sha(raw.encode()),render_sha256=page.render_sha256,width_px=page.width_px,height_px=page.height_px))
            db.add(PageFeature(page_id=page.id,encoder_sha256=sha((ROOT/'configs/colpali_local.json').read_bytes()),tensor_path='explicit-test-double.pt',tensor_sha256='a'*64,export_path='explicit-test-double.json',export_sha256='b'*64))
        self.url=f'/pages/{self.page}/regions'
        state=self.client.get(self.url+'/status').json()
        self.action={'q':'new real request but explicit inference double','document_version_id':state['document_version_id'],'render_sha256':state['render_sha256'],'index_generation':state['index_generation']}

    def post(self,action=None,headers=None):return self.client.post(self.url,json=self.action if action is None else action,headers=self.headers if headers is None else headers)
    def change(self,cls,key,**values):
        with Session(self.engine) as db,db.begin():
            row=db.get(cls,key)
            for k,v in values.items():setattr(row,k,v)

    def test_cookie_origin_csrf_first_change_and_private_boundaries(self):
        self.assertEqual(self.post(headers={'Origin':ORIGIN}).status_code,403)
        self.assertEqual(self.post(headers={**self.headers,'Origin':'https://bad.invalid'}).status_code,403)
        for name in ('B','admin'):
            self.login(name);self.headers['X-CSRF-Token']=self.client.get('/auth/me').json()['csrf_token']
            self.assertEqual(self.client.get(self.url+'/status').status_code,404)
            self.assertEqual(self.post().status_code,404)
        self.client.cookies.clear()
        for r in (self.client.get(self.url+'/status'),self.post(),self.client.get(self.url+'/3/crop')):
            self.assertEqual(r.status_code,401);self.assertEqual(r.headers['cache-control'],'private, no-store')
        self.login();self.change(User,self.owner,must_change_password=True)
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.region_worker.calls,0)

    def test_response_identity_real_png_crop_and_tampering(self):
        result=self.post();self.assertEqual(result.status_code,200,result.text)
        data=result.json();self.assertEqual(data['status'],'ready');item=data['items'][0]
        self.assertEqual((item['type'],item['layout_id'],item['bbox']),('table',3,[1.2,2.3,15.6,20.7]))
        self.assertNotIn('tensor_path',result.text);self.assertNotIn('text_source',result.text)
        crop=self.client.get(item['crop_url']);self.assertEqual(crop.status_code,200)
        self.assertEqual(Image.open(BytesIO(crop.content)).size,(15,19))
        self.assertEqual(crop.headers['cache-control'],'private, no-store')
        self.assertEqual(self.client.get(item['crop_url']+'&token=x').status_code,404)
        self.assertEqual(self.client.get(item['crop_url'].replace('/3/crop','/4/crop')).status_code,404)
        self.login('B');self.assertEqual(self.client.get(item['crop_url']).status_code,404)

    def test_version_render_index_and_extra_fields_rejected_before_forward(self):
        for update in ({'render_sha256':'a'*64},{'index_generation':'00000000-0000-4000-8000-000000000000'},
            {'document_version_id':'00000000-0000-4000-8000-000000000000'}):
            self.assertEqual(self.post({**self.action,**update}).status_code,409)
        self.assertEqual(self.post({**self.action,'tensor_path':'private'}).status_code,422)
        self.assertEqual(self.post({**self.action,'q':' '}).status_code,422)
        self.assertEqual(self.region_worker.calls,0)

    def test_session_revoked_during_inference_returns401(self):
        def revoke():
            with Session(self.engine) as db,db.begin():
                for row in db.scalars(select(AuthSession)):row.revoked_at=1
        self.region_worker.callback=revoke
        self.assertEqual(self.post().status_code,401)

    def test_document_withdrawn_during_forward_returns404(self):
        self.region_worker.callback=lambda:self.change(Document,self.doc,status='deleted')
        self.assertEqual(self.post().status_code,404)

    def test_model_failure_keeps_page_accessible_and_is_explicit(self):
        self.region_worker.failure=True
        result=self.post();self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['status'],'failed');self.assertEqual(result.json()['items'],[])
        hit=self.client.get('/search',params={'q':'query','k':1}).json()['items'][0]
        self.assertEqual(self.client.get(hit['preview_url']).status_code,200)

    def test_no_candidates_parser_failed_and_no_full_feature_short_circuit(self):
        self.change(PageParse,(self.task,self.page),status='no_candidates',candidate_count=0,candidates_json='[]',candidate_hash=sha(b'[]'))
        self.assertEqual(self.post().json()['status'],'no_candidates')
        self.change(ParsingTask,self.task,status='failed')
        self.assertEqual(self.post().json()['status'],'failed')
        with Session(self.engine) as db,db.begin():db.delete(db.get(PageFeature,self.page))
        self.assertEqual(self.post().json()['status'],'unavailable')
        self.assertEqual(self.region_worker.calls,0)

    def test_crop_rechecks_latest_task_and_current_session(self):
        url=self.post().json()['items'][0]['crop_url']
        self.change(ParsingTask,self.task,status='failed')
        self.assertEqual(self.client.get(url).status_code,404)

    def test_shared_readonly_regions_follow_current_admin_owner_visibility(self):
        with Session(self.engine) as db,db.begin():
            admin=db.scalar(select(User).where(User.username=='admin'))
            doc=db.get(Document,self.doc);doc.owner_id=admin.id;doc.visibility='shared'
        state=self.client.get(self.url+'/status')
        self.assertEqual(state.status_code,200);self.assertFalse(state.json()['can_parse'])
        ranked=self.post();self.assertEqual(ranked.status_code,200,ranked.text)
        url=ranked.json()['items'][0]['crop_url'];self.assertEqual(self.client.get(url).status_code,200)
        self.change(Document,self.doc,visibility='private')
        self.assertEqual(self.client.get(self.url+'/status').status_code,404)
        self.assertEqual(self.client.get(url).status_code,404)

    def test_nonfinite_wrong_model_and_wrong_query_never_enter_response(self):
        for mutate in (lambda r:r['regions']['rankings'][0].update(score=float('nan')),
            lambda r:r['regions'].update(d_profile_sha256='bad'),lambda r:r.update(query_sha256='bad')):
            self.region_worker.corrupt=mutate
            result=self.post();self.assertIn(result.status_code,(200,503))
            self.assertNotIn('NaN',result.text)
            if result.status_code==200:self.assertEqual(result.json()['status'],'failed')


if __name__=='__main__':unittest.main()
