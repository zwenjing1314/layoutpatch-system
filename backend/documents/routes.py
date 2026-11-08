from dataclasses import dataclass
import hashlib
import hmac
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from backend.auth.routes import load_cookie, principal
from backend.db.connection import ROOT
from backend.db.models import Document, DocumentVersion, Page, User
from .access import readable_document
from .previews import preview_token

router = APIRouter()
MAX_IMAGE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class PageFile:
    page_id: str
    document_id: str
    version_id: str
    owner_id: str
    visibility: str
    path: str
    render_sha256: str
    width: int
    height: int
    page_index: int
    access_version: int = 1


def authorized_page(db, user, page_id):
    result = db.execute(select(Page, Document).join(DocumentVersion, Page.document_version_id == DocumentVersion.id)
                        .join(Document, and_(Document.id == DocumentVersion.document_id,
                                             Document.active_version_id == DocumentVersion.id))
                        .join(User, User.id == Document.owner_id)
                        .where(Page.id == page_id, readable_document(user))).one_or_none()
    if result is None:
        raise HTTPException(404, "PAGE_NOT_FOUND")
    page, doc = result
    return PageFile(page.id, doc.id, page.document_version_id, doc.owner_id, doc.visibility,
                    page.image_path, page.render_sha256, page.width_px, page.height_px, page.page_index, doc.access_version)


def read_verified_image(page):
    # No caller-controlled paths, static mounts, redirect, streaming or 304 path.
    # Read once and hash those same bytes before the final authorization check.
    try:
        base = (ROOT / "runtime/corpus").resolve()
        path = (ROOT / page.path.replace("\\", "/")).resolve()
        if not path.is_relative_to(base) or not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError()
        with path.open("rb") as stream:
            data = stream.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES or hashlib.sha256(data).hexdigest() != page.render_sha256:
            raise ValueError()
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG" or image.mode != "RGB" or image.size != (page.width, page.height):
                raise ValueError()
            image.verify()
        return data
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(503, "PREVIEW_UNAVAILABLE") from None


@router.get("/pages/{page_id}/image", response_class=Response, operation_id="get_page_image", tags=["pages"],
            responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
            dependencies=[Depends(load_cookie)])
def page_image(page_id: str, request: Request, preview: str | None = None):
    # Optional in schema so missing credentials still reach the auth boundary;
    # exact token/duplicate/extra-parameter checks below deliberately return404.
    with Session(request.app.state.engine) as db:
        row, user = principal(request, db, require_changed=True)
        identity = (user.id, user.role, user.auth_version, row.token_hash)
        page = authorized_page(db, user, page_id)
        values = request.query_params.getlist("preview")
        if (set(request.query_params) != {"preview"} or len(values) != 1 or len(values[0]) != 64
                or not hmac.compare_digest(values[0].encode(), preview_token(row, page.page_id, page.render_sha256, page.access_version).encode())):
            raise HTTPException(404, "PAGE_NOT_FOUND")
    data = read_verified_image(page)
    with Session(request.app.state.engine) as db:
        row, user = principal(request, db, require_changed=True)
        current = authorized_page(db, user, page_id)
        if identity != (user.id, user.role, user.auth_version, row.token_hash) or current != page:
            raise HTTPException(404, "PAGE_NOT_FOUND")
    return Response(data, media_type="image/png", headers={
        "Content-Disposition": f'inline; filename="page-{page.page_index+1}.png"',
        "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
