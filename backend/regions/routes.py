"""Session-authorized region inference and original-PNG crops; no static artifacts."""
import hashlib
import hmac
from io import BytesIO
import json
import math
from typing import Literal
from uuid import UUID

from fastapi import APIRouter,Depends,HTTPException,Request,Response
from PIL import Image
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.routes import load_cookie,principal,check_csrf
from backend.db.connection import ROOT
from backend.db.models import PageFeature,PageParse,ParserProfile,ParsingTask
from backend.db.seed import canonical,sha
from backend.documents.routes import authorized_page,read_verified_image
from backend.parsing.adapter import load_profile as parser_profile
from backend.parsing.candidates import ParseError
from backend.search.qdrant import SearchUnavailable
from backend.search.scope import allowed_scope
from backend.search.worker import SearchBusy
from .service import prepare_request,rank_regions

router=APIRouter(dependencies=[Depends(load_cookie)])


class RegionState(BaseModel):
    document_id:str
    document_version_id:str
    page_id:str
    page_number:int
    render_sha256:str
    width_px:int
    height_px:int
    index_generation:str
    status:Literal['not_requested','queued','running','ready','no_candidates','failed','timeout','interrupted','unavailable']
    can_parse:bool
    task_id:str|None=None
    candidate_hash:str|None=None
    parser_profile_sha256:str|None=None
    model_profile_sha256:str
    error_code:str|None=None


class RegionInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    q:str=Field(min_length=1,max_length=2000)
    document_version_id:UUID
    render_sha256:str=Field(pattern='^[0-9a-f]{64}$')
    index_generation:UUID


class RegionItem(BaseModel):
    candidate_id:str
    layout_id:int
    rank:int
    score:float=Field(allow_inf_nan=False)
    type:Literal['text','title','image','table','equation']
    bbox:tuple[float,float,float,float]
    crop_url:str


class RegionResponse(RegionState):
    query_sha256:str|None=None
    items:list[RegionItem]


def model_identity():
    data=(ROOT/'configs/d_no_text_local.json').read_bytes()
    config=json.loads(data)
    if config['variant']!='D-no-text' or config['checkpoint_sha256']!='18b7ce737b781734560439632137b86cb3ecca017e104cbe587b79a446e47f7b':
        raise SearchUnavailable('Region model identity mismatch')
    return sha(data)


def session_identity(row,user):
    return row.token_hash,user.id,user.role,user.auth_version,row.csrf_token


def state_for(db,user,page_id):
    page=authorized_page(db,user,page_id)
    scope=allowed_scope(db,user,page.document_id)
    model=model_identity()
    result=RegionState(document_id=page.document_id,document_version_id=page.version_id,page_id=page_id,
        page_number=page.page_index+1,render_sha256=page.render_sha256,width_px=page.width,height_px=page.height,
        index_generation=scope.index_id,status='not_requested',can_parse=False,model_profile_sha256=model)
    feature=db.get(PageFeature,page_id)
    if not feature or feature.encoder_sha256!=scope.encoder_sha256:
        return result.model_copy(update={'status':'unavailable','error_code':'FULL_PAGE_FEATURE_UNAVAILABLE'}),scope
    result.can_parse=page.owner_id==user.id
    expected=sha(canonical(parser_profile()).encode())
    task=db.scalar(select(ParsingTask).join(ParserProfile,ParserProfile.id==ParsingTask.parser_profile_id).where(
        ParsingTask.document_version_id==page.version_id,ParserProfile.config_sha256==expected)
        .order_by(ParsingTask.attempt.desc()).limit(1))
    if task:
        record=db.get(PageParse,(task.id,page_id))
        result.task_id=task.id;result.parser_profile_sha256=expected
        result.candidate_hash=record.candidate_hash if record else None
        result.error_code=record.error_code if record else task.error_code
        if task.status in {'queued','running'}:result.status=task.status
        elif record and record.status in {'ready','no_candidates'} and task.status in {'ready','partial'}:result.status=record.status
        else:result.status=record.status if record and record.status in {'failed','timeout','interrupted'} else 'failed'
    return result,scope


def bound(state,action):
    if (state.document_version_id,state.render_sha256,state.index_generation)!=(str(action.document_version_id),action.render_sha256,str(action.index_generation)):
        raise HTTPException(409,'REGION_INPUT_CHANGED')


def crop_token(row,page_id,task_id,candidate_hash,model,layout_id,render):
    data=f'region-crop-v1:{page_id}:{task_id}:{candidate_hash}:{model}:{layout_id}:{render}'.encode()
    return hmac.new(row.csrf_token.encode(),data,hashlib.sha256).hexdigest()


@router.get('/pages/{page_id}/regions/status',response_model=RegionState,operation_id='get_region_status',tags=['pages'])
def get_status(page_id:str,request:Request):
    try:
        with Session(request.app.state.engine) as db:
            _,user=principal(request,db,require_changed=True)
            state,_=state_for(db,user,page_id)
            return state
    except (OSError,ValueError,KeyError,SearchUnavailable):
        raise HTTPException(503,'REGION_UNAVAILABLE') from None


@router.post('/pages/{page_id}/regions',response_model=RegionResponse,operation_id='rank_page_regions',tags=['pages'])
def rank_page(page_id:str,action:RegionInput,request:Request):
    try:
        with Session(request.app.state.engine) as db:
            row,user=principal(request,db,require_changed=True);check_csrf(request,row)
            identity=session_identity(row,user)
            state,scope=state_for(db,user,page_id);bound(state,action)
            if state.status!='ready':return RegionResponse(**state.model_dump(),items=[])
            initial=prepare_request(db,user,page_id,state.task_id,scope.encoder_sha256)
        # No database read snapshot is held across inference.
        try:
            with Session(request.app.state.engine) as db:
                _,user=principal(request,db,require_changed=True)
                ranked=rank_regions(db,user,page_id,state.task_id,action.q,request.app.state.model_worker,scope.encoder_sha256)
            error=None
        except SearchBusy:ranked=None;error='MODEL_BUSY'
        except (SearchUnavailable,ParseError,ValueError,KeyError,TypeError):ranked=None;error='REGION_INFERENCE_FAILED'
        with Session(request.app.state.engine) as db:
            row,user=principal(request,db,require_changed=True)
            current,current_scope=state_for(db,user,page_id);bound(current,action)
            if (identity!=session_identity(row,user) or current!=state or current_scope!=scope
                    or prepare_request(db,user,page_id,state.task_id,scope.encoder_sha256)!=initial):
                raise HTTPException(409,'REGION_INPUT_CHANGED')
            if error:return RegionResponse(**state.model_copy(update={'status':'failed','error_code':error}).model_dump(),items=[])
            if (ranked['d_profile_sha256']!=state.model_profile_sha256 or ranked['query_sha256']!=sha(action.q.encode())
                    or ranked['status']!='ready'):
                raise SearchUnavailable('Region result identity mismatch')
            candidates={c['candidate_id']:c for c in initial['candidates']}
            items=[]
            for r in ranked['rankings']:
                c=candidates[r['candidate_id']]
                token=crop_token(row,page_id,state.task_id,state.candidate_hash,state.model_profile_sha256,r['layout_id'],state.render_sha256)
                url=f'/pages/{page_id}/regions/{r["layout_id"]}/crop?task={state.task_id}&candidate_hash={state.candidate_hash}&model={state.model_profile_sha256}&token={token}'
                items.append(RegionItem(**r,type=c['type'],bbox=c['bbox'],crop_url=url))
            return RegionResponse(**state.model_dump(),query_sha256=ranked['query_sha256'],items=items)
    except (OSError,ValueError,KeyError,SearchUnavailable,ParseError):
        raise HTTPException(503,'REGION_UNAVAILABLE') from None


@router.get('/pages/{page_id}/regions/{layout_id}/crop',response_class=Response,operation_id='get_region_crop',tags=['pages'],
    responses={200:{'content':{'image/png':{'schema':{'type':'string','format':'binary'}}}}})
def get_crop(page_id:str,layout_id:int,request:Request,task:str='',candidate_hash:str='',model:str='',token:str=''):
    def checked(db):
        row,user=principal(request,db,require_changed=True)
        page=authorized_page(db,user,page_id)
        expected={'task','candidate_hash','model','token'}
        if (set(request.query_params)!=expected or any(len(request.query_params.getlist(k))!=1 for k in expected)
                or len(candidate_hash)!=64 or len(model)!=64 or len(token)!=64 or model!=model_identity()):
            raise HTTPException(404,'REGION_NOT_FOUND')
        scope=allowed_scope(db,user,page.document_id)
        current,_=state_for(db,user,page_id)
        if current.status!='ready' or current.task_id!=task or current.candidate_hash!=candidate_hash:
            raise HTTPException(404,'REGION_NOT_FOUND')
        inputs=prepare_request(db,user,page_id,task,scope.encoder_sha256)
        if inputs['identity']['candidate_hash']!=candidate_hash:
            raise HTTPException(404,'REGION_NOT_FOUND')
        candidate=next((c for c in inputs['candidates'] if c['layout_id']==layout_id),None)
        actual=crop_token(row,page_id,task,candidate_hash,model,layout_id,page.render_sha256)
        if not candidate or not hmac.compare_digest(actual.encode(),token.encode()):
            raise HTTPException(404,'REGION_NOT_FOUND')
        return session_identity(row,user),page,inputs,candidate
    try:
        with Session(request.app.state.engine) as db:before=checked(db)
        _,page,_,candidate=before
        data=read_verified_image(page)
        box=candidate['bbox'];bounds=(math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3]))
        output=BytesIO()
        with Image.open(BytesIO(data)) as image:image.crop(bounds).save(output,format='PNG')
        with Session(request.app.state.engine) as db:
            if checked(db)!=before:raise HTTPException(404,'REGION_NOT_FOUND')
        return Response(output.getvalue(),media_type='image/png',headers={'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Content-Disposition':f'inline; filename="region-{layout_id}.png"'})
    except (OSError,ValueError,KeyError,SearchUnavailable,ParseError):
        raise HTTPException(404,'REGION_NOT_FOUND') from None
