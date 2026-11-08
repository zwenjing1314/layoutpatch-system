"""Persistent, explicitly requested parser attempts independent from retrieval readiness."""
import json
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Document, DocumentVersion, Page, ParserProfile, ParsingTask, PageParse, User, now
from backend.db.seed import canonical, sha
from backend.documents.pipeline import write_transaction
from backend.documents.routes import PageFile, read_verified_image
from .adapter import load_profile, parse_page, verify_resources
from .candidates import ParseError

TERMINAL = {"ready","no_candidates","failed","timeout","interrupted"}


def enqueue(db, document, *, retry_task_id=None):
    if document.status != "ready" or not document.active_version_id or document.deleted_at:
        raise ParseError("DOCUMENT_NOT_READY")
    config = canonical(load_profile())
    config_sha = sha(config.encode())
    profile = db.scalar(select(ParserProfile).where(ParserProfile.config_sha256 == config_sha))
    if profile is None:
        profile = ParserProfile(config_json=config, config_sha256=config_sha)
        db.add(profile)
        db.flush()
    elif sha(profile.config_json.encode()) != profile.config_sha256 or profile.config_json != config:
        raise ParseError("PARSER_PROFILE_CHANGED")
    latest = db.scalar(select(ParsingTask).where(ParsingTask.document_version_id == document.active_version_id,
        ParsingTask.parser_profile_id == profile.id).order_by(ParsingTask.attempt.desc()).limit(1))
    if latest and retry_task_id is None:
        return latest
    if retry_task_id is not None and (not latest or latest.id != retry_task_id or latest.status not in {"failed","partial","interrupted"} or latest.attempt >= 10):
        raise ParseError("PARSER_RETRY_CONFLICT")
    task = ParsingTask(document_version_id=document.active_version_id, parser_profile_id=profile.id, attempt=latest.attempt+1 if latest else 1, status="queued")
    db.add(task)
    db.flush()
    pages = list(db.scalars(select(Page).where(Page.document_version_id == document.active_version_id).order_by(Page.page_index)))
    version = db.get(DocumentVersion, document.active_version_id)
    if [p.page_index for p in pages] != list(range(version.page_count)):
        raise ParseError("PARSER_PAGES_INCOMPLETE")
    for page in pages:
        db.add(PageParse(task_id=task.id,page_id=page.id,render_sha256=page.render_sha256,width_px=page.width_px,height_px=page.height_px))
    db.flush()
    return task


def recover(engine):
    with write_transaction(engine) as db:
        for task in db.scalars(select(ParsingTask).where(ParsingTask.status == "running")):
            task.status, task.error_code, task.updated_at = "interrupted","PARSER_INTERRUPTED",now()
            for page in db.scalars(select(PageParse).where(PageParse.task_id == task.id, PageParse.status.in_(["pending","running"]))):
                page.status,page.error_code,page.updated_at = "interrupted","PARSER_INTERRUPTED",now()


def authority(db, task):
    version = db.get(DocumentVersion,task.document_version_id)
    doc = db.get(Document,version.document_id) if version else None
    user = db.get(User,doc.owner_id) if doc else None
    if not doc or not user or not user.active or doc.deleted_at or doc.status != "ready" or doc.active_version_id != task.document_version_id:
        raise ParseError("PARSER_AUTHORITY_CHANGED")
    return version,doc


class ParsingRunner:
    def __init__(self, engine, parser=parse_page, verifier=verify_resources):
        self.engine,self.parser,self.verifier = engine,parser,verifier
        self.stop_event,self.thread = threading.Event(),None

    def start(self):
        self.thread = threading.Thread(target=self.loop,name="private-mineru-parser",daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=610)
            if self.thread.is_alive():
                raise RuntimeError("Parser did not stop within bounded page lifetime")

    def loop(self):
        while not self.stop_event.is_set():
            try:
                if self.run_one():
                    continue
            except Exception:
                pass  # No private text, paths or exception details in service logs.
            self.stop_event.wait(1)

    def run_one(self):
        with write_transaction(self.engine) as db:
            task = db.scalar(select(ParsingTask).where(ParsingTask.status == "queued").order_by(ParsingTask.created_at,ParsingTask.id).limit(1))
            if task is None:
                return False
            task.status,task.updated_at = "running",now()
            task_id = task.id
        started = time.monotonic()
        try:
            with Session(self.engine,expire_on_commit=False) as db:
                task = db.get(ParsingTask,task_id)
                version,doc = authority(db,task)
                profile = db.get(ParserProfile,task.parser_profile_id)
                if sha(profile.config_json.encode()) != profile.config_sha256:
                    raise ParseError("PARSER_PROFILE_CHANGED")
                config = json.loads(profile.config_json)
                pages = list(db.scalars(select(Page).where(Page.document_version_id == version.id).order_by(Page.page_index)))
                if [p.page_index for p in pages] != list(range(version.page_count)):
                    raise ParseError("PARSER_PAGES_INCOMPLETE")
            self.verifier(config)
            for page in pages:
                if self.stop_event.is_set():
                    raise ParseError("PARSER_INTERRUPTED")
                if time.monotonic()-started >= 900:
                    raise ParseError("PARSER_DEADLINE_EXCEEDED")
                with write_transaction(self.engine) as db:
                    current = db.get(ParsingTask,task_id)
                    current_version,current_doc = authority(db,current)
                    actual = db.get(Page,page.id)
                    if (current.status != "running" or current_version.pdf_sha256 != version.pdf_sha256 or current_version.pdf_path != version.pdf_path
                            or (actual.document_version_id,actual.page_index,actual.render_sha256,actual.width_px,actual.height_px,actual.image_path)
                            != (page.document_version_id,page.page_index,page.render_sha256,page.width_px,page.height_px,page.image_path)):
                        raise ParseError("PARSER_INPUT_CHANGED")
                    stored = db.get(PageParse,(task_id,page.id))
                    stored.status,stored.updated_at = "running",now()
                try:
                    read_verified_image(PageFile(page.id,doc.id,version.id,doc.owner_id,doc.visibility,page.image_path,page.render_sha256,page.width_px,page.height_px,page.page_index))
                    candidates,provenance = self.parser(task_id,version,page,config)
                    encoded = canonical(candidates)
                    with write_transaction(self.engine) as db:
                        current = db.get(ParsingTask,task_id)
                        current_version,_ = authority(db,current)
                        if (current_version.pdf_sha256,current_version.pdf_path,current_version.page_count,current_version.render_profile_sha256) != (version.pdf_sha256,version.pdf_path,version.page_count,version.render_profile_sha256):
                            raise ParseError("PARSER_INPUT_CHANGED")
                        actual = db.get(Page,page.id)
                        if self.stop_event.is_set() or current.status != "running":
                            raise ParseError("PARSER_INTERRUPTED")
                        if (actual.render_sha256,actual.document_version_id,actual.width_px,actual.height_px) != (page.render_sha256,version.id,page.width_px,page.height_px):
                            raise ParseError("PARSER_INPUT_CHANGED")
                        stored = db.get(PageParse,(task_id,page.id))
                        stored.status,stored.candidates_json,stored.candidate_count = "ready" if candidates else "no_candidates",encoded,len(candidates)
                        stored.candidate_hash,stored.provenance_json,stored.updated_at = sha(encoded.encode()),canonical(provenance),now()
                except ParseError as exc:
                    if exc.code in {"PARSER_AUTHORITY_CHANGED","PARSER_INTERRUPTED","PARSER_INPUT_CHANGED"}:
                        raise
                    self.fail_page(task_id,page.id,exc.code)
                except Exception:
                    self.fail_page(task_id,page.id,"PARSER_EXECUTION_FAILED")
            with write_transaction(self.engine) as db:
                task = db.get(ParsingTask,task_id)
                authority(db,task)
                if self.stop_event.is_set() or task.status != "running":
                    raise ParseError("PARSER_INTERRUPTED")
                states = list(db.scalars(select(PageParse.status).where(PageParse.task_id == task_id)))
                successes = sum(s in {"ready","no_candidates"} for s in states)
                task.status = "ready" if successes == len(pages) else "partial" if successes else "failed"
                task.error_code = None if task.status == "ready" else "PARSER_PAGE_ERRORS"
                task.updated_at = now()
        except Exception as exc:
            code = exc.code if isinstance(exc,ParseError) else "PARSER_EXECUTION_FAILED"
            with write_transaction(self.engine) as db:
                task = db.get(ParsingTask,task_id)
                task.status,task.error_code,task.updated_at = "interrupted" if code == "PARSER_INTERRUPTED" else "failed",code,now()
                for page in db.scalars(select(PageParse).where(PageParse.task_id == task_id,PageParse.status.in_(["pending","running"]))):
                    page.status,page.error_code,page.updated_at = "interrupted" if code == "PARSER_INTERRUPTED" else "timeout" if code in {"PARSER_TIMEOUT","PARSER_DEADLINE_EXCEEDED"} else "failed",code,now()
        return True

    def fail_page(self,task_id,page_id,code):
        with write_transaction(self.engine) as db:
            page = db.get(PageParse,(task_id,page_id))
            page.status,page.error_code,page.updated_at = "timeout" if code == "PARSER_TIMEOUT" else "failed",code,now()
