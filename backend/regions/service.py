"""Authorized internal D input assembly; no torch in the web environment."""
import math
from fastapi import HTTPException

from backend.db.models import DocumentVersion, Page, PageFeature, User
from backend.parsing.store import read_candidates
from backend.parsing.candidates import ParseError
from backend.search.scope import allowed_scope


def prepare_request(db,user,page_id,task_id,expected_encoder):
    current=db.get(User,user.id)
    if current is None or not current.active or current.must_change_password:
        raise HTTPException(403,'REGION_PRINCIPAL_UNAVAILABLE')
    candidates,parser=read_candidates(db,user,page_id,task_id)
    page=db.get(Page,page_id)
    feature=db.get(PageFeature,page_id)
    if feature is None or feature.encoder_sha256!=expected_encoder:
        raise ParseError('FULL_PAGE_FEATURE_UNAVAILABLE')
    # The authorized reader checks active document/version; the worker verifies
    # exact feature bytes/schema/render/encoder and the whole canonical candidate set.
    version=db.get(DocumentVersion,page.document_version_id)
    scope=allowed_scope(db,user,version.document_id)
    indexed=next((p for p in scope.pages if p.id==page_id),None)
    if scope.encoder_sha256!=expected_encoder or indexed is None:
        raise ParseError('FULL_PAGE_INDEX_MISMATCH')
    identity={'document_id':version.document_id,'document_version_id':version.id,'page_id':page_id,
        'page_index':page.page_index,'page_number':page.page_index+1,'width_px':page.width_px,'height_px':page.height_px,
        **parser,'parsing_task_id':task_id,'encoder_sha256':feature.encoder_sha256,'tensor_sha256':feature.tensor_sha256,
        'index_generation':scope.index_id,'pipeline_profile_id':scope.profile_id,'embedding_sha256':indexed.embedding_sha256}
    return {'identity':identity,'candidates':candidates,'tensor_path':feature.tensor_path}


def rank_regions(db,user,page_id,task_id,question,worker,expected_encoder):
    """Internal caller supplies its current principal; no cookie/session boundary yet.

    Stage 2-6 must revalidate its session around this potentially long operation.
    """
    if not isinstance(question,str) or not question.strip() or len(question)>2000:
        raise ValueError('Invalid question')
    principal_identity=(user.id,user.role,user.auth_version)
    request=prepare_request(db,user,page_id,task_id,expected_encoder)
    access_scope=allowed_scope(db,user,request['identity']['document_id']).fingerprint
    result=worker.rank_regions(question,request,expected_encoder)
    # End the read transaction so a concurrent revocation/version replacement
    # cannot be hidden by the ORM identity map or a SQLite read snapshot.
    db.rollback()
    if (principal_identity!=(user.id,user.role,user.auth_version)
            or prepare_request(db,user,page_id,task_id,expected_encoder)!=request
            or allowed_scope(db,user,request['identity']['document_id']).fingerprint!=access_scope):
        raise ParseError('REGION_INPUT_CHANGED')
    rankings=result['regions']['rankings']
    ids={c['candidate_id']:c['layout_id'] for c in request['candidates']}
    if (len(rankings)!=len(ids) or {r['candidate_id'] for r in rankings}!=set(ids)
            or any(r['rank']!=i+1 or r['layout_id']!=ids[r['candidate_id']] or not math.isfinite(r['score']) for i,r in enumerate(rankings))):
        raise ParseError('REGION_RESULT_MISMATCH')
    return {'identity':request['identity'],**result['regions'],'query_sha256':result['query_sha256']}
