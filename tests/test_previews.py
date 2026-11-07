"""Real SQLite, actual PNG bytes, current authorization and session replay."""
import secrets
import unittest
from unittest.mock import patch

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.auth.accounts import change_account
from backend.db.models import Document, DocumentVersion, Page, User
from backend.documents.routes import read_verified_image
from tests import test_search as search_tests


class PreviewTests(unittest.TestCase):
    setUp = search_tests.SearchTests.setUp
    tearDown = search_tests.SearchTests.tearDown
    login = search_tests.SearchTests.login
    search = search_tests.SearchTests.search
    status = search_tests.SearchTests.status

    def own_hit(self):
        self.login()
        return self.search().json()['items'][0]

    def test_image_identity_headers_and_conditional_requests(self):
        hit = self.own_hit()
        response = self.client.get(hit['preview_url'])
        self.status(response, 200)
        self.assertEqual(response.headers['content-type'], 'image/png')
        self.assertEqual(response.headers['vary'], 'Cookie')
        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
        self.assertEqual(response.headers['referrer-policy'], 'no-referrer')
        self.assertTrue(response.content.startswith(b'\x89PNG\r\n\x1a\n'))
        import hashlib
        self.assertEqual(hashlib.sha256(response.content).hexdigest(), hit['render_sha256'])
        self.assertNotIn('etag', response.headers)
        self.assertNotIn('last-modified', response.headers)
        self.status(self.client.get(hit['preview_url'], headers={'If-None-Match':'*','Range':'bytes=0-1'}), 200)

    def test_unauthenticated_first_change_and_private_page_enumeration(self):
        hit = self.own_hit()
        self.client.cookies.clear()
        self.status(self.client.get(hit['preview_url']), 401)
        self.login('B')
        with self.app.state.engine.begin() as c:
            c.execute(update(User).where(User.username=='B').values(must_change_password=True))
        self.status(self.client.get(hit['preview_url']), 403)
        with self.app.state.engine.begin() as c:
            c.execute(update(User).where(User.username=='B').values(must_change_password=False))
        denied = self.client.get(hit['preview_url']); self.status(denied, 404)
        absent = self.client.get('/pages/unknown/image?preview='+'a'*64); self.status(absent, 404)
        self.assertEqual(denied.json(), absent.json())
        self.login('admin'); self.status(self.client.get(hit['preview_url']), 404)

    def test_preview_bound_to_page_and_issuing_session(self):
        hit = self.own_hit()
        url = hit['preview_url']; path = url.split('?')[0]
        for invalid in (path, url+'&preview=x', url+'&path=anything', path+'?preview=wrong'):
            self.status(self.client.get(invalid), 404)
        other = self.search().json()['items'][1]
        self.status(self.client.get(url.replace(hit['page_id'], other['page_id'])), 404)
        self.login('A')
        self.status(self.client.get(url), 404)
        fresh = self.search().json()['items'][0]['preview_url']
        self.status(self.client.get(fresh), 200)

    def test_logout_password_revoke_and_disable_reject_old_cookie(self):
        for action in ('logout', 'password', 'revoke', 'disable'):
            self.client.cookies.clear()
            hit = self.own_hit(); token = self.client.cookies.get('layoutpatch_session')
            csrf = self.client.get('/auth/me').json()['csrf_token']
            headers = {'Origin':'http://127.0.0.1:3000','X-CSRF-Token':csrf,'Content-Type':'application/json'}
            if action=='logout': self.status(self.client.post('/auth/logout',headers=headers),204)
            elif action=='password':
                new=secrets.token_urlsafe(24)
                self.status(self.client.post('/auth/password',json={'current_password':self.passwords['A'],'new_password':new},headers=headers),204)
                self.passwords['A']=new
            else: change_account(self.engine,'A',action,self.app.state.clock())
            self.client.cookies.clear(); self.client.cookies.set('layoutpatch_session',token)
            self.status(self.client.get(hit['preview_url'],headers={'If-None-Match':'*'}),401)

    def test_shared_withdrawal_inactive_owner_and_session_switch(self):
        hit = self.own_hit()
        with Session(self.engine) as db, db.begin():
            original = db.get(Document, hit['document_id'])
            source = db.get(DocumentVersion, original.active_version_id)
            page = db.get(Page,hit['page_id'])
            admin = db.scalar(select(User).where(User.username=='admin'))
            doc = Document(source_key='preview-shared',owner_id=admin.id,display_name='Separate shared preview',visibility='shared',status='ready')
            db.add(doc); db.flush()
            version = DocumentVersion(document_id=doc.id,version=1,pdf_sha256=source.pdf_sha256,pdf_path=source.pdf_path,page_count=1,
                                      render_profile_json=source.render_profile_json,render_profile_sha256=source.render_profile_sha256)
            db.add(version);db.flush();doc.active_version_id=version.id
            shared = Page(document_version_id=version.id,source_page_id='preview-shared:p0',page_index=0,width_px=page.width_px,height_px=page.height_px,
                          render_sha256=page.render_sha256,image_path=page.image_path)
            db.add(shared);db.flush(); shared_id,doc_id,admin_id=shared.id,doc.id,admin.id
        from backend.documents.previews import preview_url
        from backend.auth.store import digest
        from backend.db.models import AuthSession
        def url():
            with Session(self.engine) as db:
                row=db.get(AuthSession,digest(self.client.cookies.get('layoutpatch_session')))
                return preview_url(row,shared_id,hit['render_sha256'])
        a_url=url();self.status(self.client.get(a_url),200)
        self.login('B');self.status(self.client.get(a_url),404)
        b_url=url();self.status(self.client.get(b_url),200)
        with self.engine.begin() as c:c.execute(update(Document).where(Document.id==doc_id).values(visibility='private'))
        self.status(self.client.get(b_url),404)
        with self.engine.begin() as c:
            c.execute(update(Document).where(Document.id==doc_id).values(visibility='shared'))
            c.execute(update(User).where(User.id==admin_id).values(active=False))
        self.status(self.client.get(b_url),404)
        with self.engine.begin() as c:c.execute(update(User).where(User.id==admin_id).values(active=True,role='user'))
        self.status(self.client.get(b_url),404)

    def test_deleted_noncurrent_and_missing_files_fail_closed(self):
        hit=self.own_hit()
        with self.engine.begin() as c:c.execute(update(Document).where(Document.id==hit['document_id']).values(status='deleted'))
        self.status(self.client.get(hit['preview_url']),404)
        with self.engine.begin() as c:c.execute(update(Document).where(Document.id==hit['document_id']).values(status='ready',active_version_id=None))
        self.status(self.client.get(hit['preview_url']),404)
        with self.engine.begin() as c:
            c.execute(update(Document).where(Document.id==hit['document_id']).values(active_version_id=hit['document_version_id']))
            c.execute(update(Page).where(Page.id==hit['page_id']).values(image_path='runtime/corpus/absent.png'))
        self.status(self.client.get(hit['preview_url']),503)

    def test_path_escape_and_integrity_failure_never_returns_bytes(self):
        hit=self.own_hit()
        for values in ({'image_path':'../layoutpatch/README.md'},{'image_path':'runtime/metadata.sqlite3'},{'render_sha256':'f'*64}):
            with Session(self.engine) as db,db.begin():
                page=db.get(Page,hit['page_id']);original={k:getattr(page,k) for k in values}
                for k,v in values.items():setattr(page,k,v)
            if 'render_sha256' in values:
                url=self.search().json()['items'][0]['preview_url']
            else:url=hit['preview_url']
            self.status(self.client.get(url),503)
            with Session(self.engine) as db,db.begin():
                for k,v in original.items():setattr(db.get(Page,hit['page_id']),k,v)

    def test_revocation_or_permission_change_during_file_read(self):
        hit=self.own_hit()
        def revoke(page):
            data=read_verified_image(page);change_account(self.engine,'A','revoke',self.app.state.clock());return data
        with patch('backend.documents.routes.read_verified_image',side_effect=revoke):self.status(self.client.get(hit['preview_url']),401)
        hit=self.own_hit()
        def delete(page):
            data=read_verified_image(page)
            with self.engine.begin() as c:c.execute(update(Document).where(Document.id==page.document_id).values(deleted_at='test'))
            return data
        with patch('backend.documents.routes.read_verified_image',side_effect=delete):self.status(self.client.get(hit['preview_url']),404)

    def test_no_static_file_or_pdf_bypass(self):
        self.login()
        for path in ('/files/test.png','/runtime/corpus/manifest.json','/storage/test.png','/documents/anything/pdf','/pages/anything/thumbnail'):
            self.assertEqual(self.client.get(path).status_code,404)


if __name__=='__main__':unittest.main(verbosity=2)
