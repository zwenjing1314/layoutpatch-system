"""Internal verified candidate reader for later D integration. No public region route."""
import json
from sqlalchemy import select
from backend.db.models import Page, PageParse, ParserProfile, ParsingTask
from backend.db.seed import canonical,sha
from backend.documents.routes import authorized_page
from .candidates import ParseError,finite_box


def read_candidates(db,user,page_id,task_id):
    """Reauthorize current page, then verify immutable candidate identity before reuse."""
    authorized=authorized_page(db,user,page_id)
    page=db.get(Page,page_id)
    task=db.get(ParsingTask,task_id)
    record=db.get(PageParse,(task_id,page_id))
    if (not task or task.document_version_id!=authorized.version_id or task.status not in {'ready','partial'}
            or not record or record.status not in {'ready','no_candidates'}):
        raise ParseError('CANDIDATES_UNAVAILABLE')
    profile=db.get(ParserProfile,task.parser_profile_id)
    try:
        if (sha(profile.config_json.encode())!=profile.config_sha256 or sha(record.candidates_json.encode())!=record.candidate_hash
                or (record.render_sha256,record.width_px,record.height_px)!=(page.render_sha256,page.width_px,page.height_px)):
            raise ValueError()
        candidates=json.loads(record.candidates_json)
        if canonical(candidates)!=record.candidates_json or len(candidates)!=record.candidate_count:
            raise ValueError()
        expected={'document_id':authorized.document_id,'document_version_id':authorized.version_id,'page_id':page_id,
            'page_index':authorized.page_index,'page_number':authorized.page_index+1,'render_sha256':authorized.render_sha256,
            'width_px':authorized.width,'height_px':authorized.height,'parser_profile_sha256':profile.config_sha256}
        ids=set()
        for item in candidates:
            if (any(item.get(k)!=v for k,v in expected.items()) or not finite_box(item.get('bbox'),[authorized.width,authorized.height])
                    or item['candidate_id'] in ids or item['candidate_id']!=f"{page_id}:block:{item['layout_id']}"
                    or item['coordinate_system']!='original_png_pixel_xyxy_top_left'):
                raise ValueError()
            ids.add(item['candidate_id'])
        if bool(candidates)!=(record.status=='ready'):
            raise ValueError()
        return candidates,{'parser_profile_id':profile.id,'parser_profile_sha256':profile.config_sha256,'candidate_hash':record.candidate_hash,'render_sha256':record.render_sha256}
    except (ValueError,TypeError,KeyError,AttributeError):
        raise ParseError('CANDIDATE_IDENTITY_MISMATCH') from None
