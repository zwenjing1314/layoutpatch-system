"""Fresh actual old-13-page authorized retrieval after new regional APIs are loaded."""
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.db.connection import ROOT,make_engine
from backend.db.models import Document,Page,PageFeature,User
from backend.db.seed import sha
from scripts.check_regions import OUT,STATE,DATABASE,ORIGIN,read
from scripts.check_regions_http import save


def main():
    checks=[];state=read(STATE);cases=[];engine=make_engine(DATABASE)
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value:raise AssertionError(name)
    for owner in ('A','B'):
        with Session(engine) as db:
            user=db.scalar(select(User).where(User.username==owner));doc=db.scalar(select(Document).where(Document.owner_id==user.id,Document.id.not_in([s['document_id'] for s in state['selected']])))
            page_ids=set(db.scalars(select(Page.id).where(Page.document_version_id==doc.active_version_id)));doc_id=doc.id
        with httpx.Client(base_url='http://127.0.0.1:8000',timeout=235,trust_env=False) as c:
            r=c.post('/auth/login',json={'username':owner,'password':state['passwords'][owner]},headers={'Origin':ORIGIN});check(owner+'_legacy_login',r.status_code==200)
            q='Which charts explain the document retrieval method and its evaluation? R22 '+owner
            r=c.get('/search',params={'q':q,'k':3,'document_id':doc_id});check(owner+'_original_pages_real_search',r.status_code==200 and len(r.json()['items'])==3)
            data=r.json();check(owner+'_only_original_authorized_pages',all(p['page_id'] in page_ids for p in data['items']))
            for item in data['items']:
                image=c.get(item['preview_url']);check(owner+'_original_PNG_'+item['page_id'],image.status_code==200 and sha(image.content)==item['render_sha256'])
                s=c.get('/pages/'+item['page_id']+'/regions/status');check(owner+'_original_no_full_feature_explicit_'+item['page_id'],s.status_code==200 and s.json()['status']=='unavailable')
            cases.append({'owner':owner,'query':q,'response':data,'authorized_page_count':len(page_ids)})
    engine.dispose()
    save(ROOT/'docs/checks/stage2-6-legacy.json',{'round':'R22','overall':'passed','checks':checks,'cases':cases,'limits':'Two real new original-page queries. Old13 images/indices retained, old pages not automatically parsed or encoded. No region fabrication for absent complete PageFeature records.'})
    print('Old13 chain',len(checks),'checks passed; two real queries')


if __name__=='__main__':main()
