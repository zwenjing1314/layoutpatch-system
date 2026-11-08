"""Retryable physical cleanup. Only explicit document-owned artifacts are removed."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import threading
import time

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.auth.accounts import account_transaction
from backend.db.connection import ROOT
from backend.db.models import (Document, DocumentCleanup, DocumentVersion, IndexGeneration, IndexPage,
                               Job, JobAttempt, Page, PageFeature, PageParse, ParsingTask, now)
from backend.db.seed import canonical, sha
from backend.search.qdrant import SearchUnavailable
from .deletion import event
from .lifecycle import cleaning


class CleanupError(RuntimeError):
    pass


@dataclass(frozen=True)
class CleanupSettings:
    roots: tuple[Path, ...] = (ROOT/'runtime/corpus', ROOT/'runtime/uploads', ROOT/'runtime/parsing', ROOT/'runtime/regions/d-no-text')
    ingest_root: Path = ROOT/'runtime/corpus/ingest'
    parsing_root: Path = ROOT/'runtime/parsing'
    cache_root: Path = ROOT/'runtime/regions/d-no-text'
    collection_prefix: str = 'layoutpatch_system_'

    def __post_init__(self):
        runtime = (ROOT/'runtime').resolve()
        if not self.collection_prefix.startswith('layoutpatch_system_') or len(self.collection_prefix) < 19:
            raise ValueError('Cleanup requires an explicit owned collection prefix')
        for path in (*self.roots, self.ingest_root, self.parsing_root, self.cache_root):
            if path.resolve() == runtime or not path.resolve().is_relative_to(runtime):
                raise ValueError('Cleanup storage must be below project runtime')


def build_manifest(db, doc, settings):
    versions = list(db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id)))
    version_ids = [v.id for v in versions]
    pages = list(db.scalars(select(Page).where(Page.document_version_id.in_(version_ids))))
    page_ids = [p.id for p in pages]
    jobs = list(db.scalars(select(Job).where(Job.document_version_id.in_(version_ids))))
    tasks = list(db.scalars(select(ParsingTask).where(ParsingTask.document_version_id.in_(version_ids))))
    files = [v.pdf_path for v in versions] + [p.image_path for p in pages]
    for feature in db.scalars(select(PageFeature).where(PageFeature.page_id.in_(page_ids))):
        files += [feature.tensor_path, feature.export_path]
    trees = [(settings.ingest_root/j.id).relative_to(ROOT).as_posix() for j in jobs]
    trees += [(settings.parsing_root/t.id).relative_to(ROOT).as_posix() for t in tasks]
    # Upload and seeded corpus directories are generated per document, never by
    # display name. Reference/path checks run before ANY physical side effect.
    for version in versions:
        parent = Path(version.pdf_path).parent
        if Path(version.pdf_path).name == 'source.pdf':
            trees.append(parent.as_posix())
    return {'schema': 'document-cleanup-v1', 'document_id': doc.id, 'version_ids': version_ids,
            'page_ids': page_ids, 'access_version': doc.access_version, 'active_version_id': doc.active_version_id,
            'files': sorted(set(files)), 'trees': sorted(set(trees))}


def checked_path(relative, settings):
    raw = Path(relative)
    if raw.is_absolute() or '..' in raw.parts:
        raise CleanupError('CLEANUP_PATH_INVALID')
    path = ROOT/raw
    # Reject junctions/symlinks even when their target happens to remain inside
    # runtime. Do not follow a reparse point while traversing an owned tree.
    current = ROOT
    for part in raw.parts:
        current = current/part
        if current.exists() or current.is_symlink():
            attributes = current.lstat()
            if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise CleanupError('CLEANUP_PATH_INVALID')
    resolved = path.resolve()
    roots = tuple(root.resolve() for root in settings.roots)
    if not any(resolved != root and resolved.is_relative_to(root) for root in roots):
        raise CleanupError('CLEANUP_PATH_INVALID')
    return path


def paths(db, doc_id, manifest, settings):
    files = [checked_path(p, settings) for p in manifest['files']]
    trees = [checked_path(p, settings) for p in manifest['trees']]
    cache = settings.cache_root
    if cache.exists():
        checked_path((cache/'sentinel').relative_to(ROOT).as_posix(), settings)
        for folder in cache.iterdir():
            checked_path(folder.relative_to(ROOT).as_posix(), settings)
            if not folder.is_dir():
                continue
            try:
                data = json.loads((folder/'manifest.json').read_text('utf-8'))
                identity = data['identity']['inputs']
                if identity['document_id'] == doc_id:
                    if identity['document_version_id'] not in manifest['version_ids']:
                        raise CleanupError('CLEANUP_CACHE_IDENTITY_INVALID')
                    trees.append(folder)
            except (OSError, KeyError, TypeError, ValueError):
                # Unattributable crash temporaries cannot safely be assigned to
                # this document. Preserve them and report incomplete cleanup.
                raise CleanupError('CLEANUP_CACHE_UNATTRIBUTED') from None
    # Never remove bytes referenced by a different document, including same-name
    # uploads, shared physical paths and a path nested below an owned directory.
    refs = list(db.execute(select(DocumentVersion.pdf_path).where(DocumentVersion.document_id != doc_id)).scalars())
    refs += list(db.execute(select(Page.image_path).join(DocumentVersion).where(DocumentVersion.document_id != doc_id)).scalars())
    for a, b in db.execute(select(PageFeature.tensor_path, PageFeature.export_path).join(Page).join(DocumentVersion).where(DocumentVersion.document_id != doc_id)):
        refs += [a, b]
    for raw in db.scalars(select(PageParse.provenance_json).join(ParsingTask).join(DocumentVersion).where(DocumentVersion.document_id != doc_id)):
        if raw:
            provenance = json.loads(raw)
            refs += [provenance[k] for k in ('raw_path', 'receipt_path') if provenance.get(k)]
    for reference in refs:
        other = (ROOT/reference).resolve()
        if any(other == p.resolve() for p in files) or any(other.is_relative_to(p.resolve()) for p in trees):
            raise CleanupError('CLEANUP_REFERENCED_FILE')
    # Validate the whole recursive inventory before removing the first file.
    for tree in trees:
        if tree.exists():
            if not tree.is_dir():
                raise CleanupError('CLEANUP_PATH_INVALID')
            for base, directories, names in os.walk(tree, followlinks=False):
                for name in directories + names:
                    checked_path((Path(base)/name).relative_to(ROOT).as_posix(), settings)
    return files, sorted(set(trees), key=lambda p: len(p.parts), reverse=True)


def remove_paths(files, trees, settings):
    for tree in trees:
        if not tree.exists():
            continue
        for base, directories, names in os.walk(tree, topdown=False, followlinks=False):
            for name in names:
                checked_path((Path(base)/name).relative_to(ROOT).as_posix(), settings).unlink(missing_ok=True)
            for name in directories:
                checked_path((Path(base)/name).relative_to(ROOT).as_posix(), settings).rmdir()
        checked_path(tree.relative_to(ROOT).as_posix(), settings).rmdir()
    for path in files:
        checked_path(path.relative_to(ROOT).as_posix(), settings).unlink(missing_ok=True)


def recover_cleanup(engine):
    with account_transaction(engine) as db:
        for task in db.scalars(select(DocumentCleanup).where(DocumentCleanup.status == 'running')):
            task.status, task.stage, task.error_code, task.updated_at = 'queued', 'waiting', 'CLEANUP_INTERRUPTED', now()


class CleanupRunner:
    def __init__(self, engine, qdrant, settings=None):
        self.engine, self.qdrant, self.settings = engine, qdrant, settings or CleanupSettings()
        self.stop_event, self.thread = threading.Event(), None

    def start(self):
        self.thread = threading.Thread(target=self.loop, name='private-document-cleanup', daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=200)
            if self.thread.is_alive():
                raise RuntimeError('Cleanup has not reached its bounded checkpoint')

    def loop(self):
        while not self.stop_event.is_set():
            try:
                if self.run_one():
                    continue
            except Exception:
                pass  # Paths, names, private content and transport errors stay private.
            self.stop_event.wait(1)

    def clean_index(self, index_id, manifest):
        with account_transaction(self.engine) as db:
            index = db.get(IndexGeneration, index_id)
            if not index.collection_name.startswith(self.settings.collection_prefix):
                raise CleanupError('CLEANUP_COLLECTION_NOT_OWNED')
            memberships = set(db.scalars(select(IndexPage.page_id).where(IndexPage.index_id == index.id)))
            targets = set(manifest['page_ids'])
            info = self.qdrant.info(index.collection_name)
            if info is None:
                if index.status == 'ready' and memberships - targets:
                    raise CleanupError('CLEANUP_INDEX_MISMATCH')
                if index.status == 'ready':
                    self.qdrant.create(index.collection_name)
                before = []
            else:
                self.qdrant.check_info(info)
                before = self.qdrant.all_points(index.collection_name)
            removed, survivors = [], []
            for point in before:
                payload, page_id = point['payload'], str(point['id'])
                belongs = payload.get('document_id') == manifest['document_id']
                if (page_id in targets and not belongs or belongs and payload.get('document_version_id') not in manifest['version_ids']):
                    raise CleanupError('CLEANUP_INDEX_MISMATCH')
                (removed if belongs else survivors).append(point)
            if index.status == 'ready' and {str(p['id']) for p in survivors} != memberships - targets:
                raise CleanupError('CLEANUP_INDEX_MISMATCH')
            if removed:
                self.qdrant.delete_points(index.collection_name, [str(p['id']) for p in removed])
            after = self.qdrant.all_points(index.collection_name) if info is not None or index.status == 'ready' else []
            canonical_points = lambda points: canonical(sorted(points, key=lambda p: str(p['id'])))
            if canonical_points(after) != canonical_points(survivors):
                raise CleanupError('CLEANUP_INDEX_MISMATCH')
            db.execute(delete(IndexPage).where(IndexPage.index_id == index.id, IndexPage.page_id.in_(targets)))
            if removed or memberships & targets:
                # Remote deletion is idempotent; a crash between wait=true and
                # this commit is reconciled from survivors on the next attempt.
                index.page_count, index.vector_count = len(after), len(after)*1031
                index.source_manifest_sha256 = sha(canonical({'schema': 'delete-v1', 'parent': index.source_manifest_sha256,
                    'document_id': manifest['document_id'], 'remaining': sorted(str(p['id']) for p in after)}).encode())
                index.feature_file_sha256 = sha(canonical({'parent': index.feature_file_sha256, 'delete': manifest['document_id']}).encode())

    def run_one(self):
        with cleaning(self.engine) as acquired:
            if not acquired:
                return False  # Tombstone already committed; wait for existing producers.
            with account_transaction(self.engine) as db:
                task = db.scalar(select(DocumentCleanup).where(DocumentCleanup.status == 'queued').order_by(DocumentCleanup.created_at, DocumentCleanup.id).limit(1))
                if task is None:
                    return False
                doc = db.get(Document, task.document_id)
                if doc.status != 'deleted' or not doc.deleted_at:
                    raise CleanupError('CLEANUP_TOMBSTONE_REQUIRED')
                task.status, task.stage, task.error_code, task.updated_at = 'running', 'indexes', None, now()
                task_id, attempt, manifest = task.id, task.attempt, json.loads(task.manifest_json)
            try:
                # Preflight all file ownership before making any index/file side effects.
                with Session(self.engine) as db:
                    paths(db, manifest['document_id'], manifest, self.settings)
                    indices = list(db.scalars(select(IndexGeneration.id)))
                for index_id in indices:
                    if self.stop_event.is_set():
                        raise CleanupError('CLEANUP_INTERRUPTED')
                    self.clean_index(index_id, manifest)
                with account_transaction(self.engine) as db:
                    task = db.get(DocumentCleanup, task_id)
                    task.stage, task.updated_at = 'files', now()
                with account_transaction(self.engine) as db:
                    files, trees = paths(db, manifest['document_id'], manifest, self.settings)
                    remove_paths(files, trees, self.settings)
                    versions, pages = manifest['version_ids'], manifest['page_ids']
                    jobs = select(Job.id).where(Job.document_version_id.in_(versions))
                    tasks = select(ParsingTask.id).where(ParsingTask.document_version_id.in_(versions))
                    doc = db.get(Document, manifest['document_id'])
                    doc.active_version_id = None
                    db.flush()
                    db.execute(delete(JobAttempt).where(JobAttempt.job_id.in_(jobs)))
                    db.execute(delete(Job).where(Job.document_version_id.in_(versions)))
                    db.execute(delete(PageParse).where(PageParse.task_id.in_(tasks)))
                    db.execute(delete(ParsingTask).where(ParsingTask.document_version_id.in_(versions)))
                    db.execute(delete(PageFeature).where(PageFeature.page_id.in_(pages)))
                    db.execute(delete(IndexPage).where(IndexPage.page_id.in_(pages)))
                    db.execute(delete(Page).where(Page.id.in_(pages)))
                    db.execute(delete(DocumentVersion).where(DocumentVersion.id.in_(versions)))
                    # Keep only tombstone/control metadata, never raw paths or candidates.
                    doc.display_name = '已删除文档'
                    doc.display_name_key = '已删除文档'
                    task = db.get(DocumentCleanup, task_id)
                    task.status, task.stage, task.error_code, task.updated_at = 'completed', 'completed', None, now()
                    task.manifest_json = canonical({k: manifest[k] for k in ('schema', 'access_version', 'active_version_id')})
                    event(db, None, doc, 'cleanup', 'success', 'OK', attempt, time.time())
            except Exception as exc:
                code = str(exc) if isinstance(exc, CleanupError) else 'CLEANUP_INDEX_UNAVAILABLE' if isinstance(exc, SearchUnavailable) else 'CLEANUP_STORAGE_FAILED' if isinstance(exc, OSError) else 'CLEANUP_FAILED'
                with account_transaction(self.engine) as db:
                    task = db.get(DocumentCleanup, task_id)
                    task.status, task.error_code, task.updated_at = 'failed', code, now()
                    event(db, None, db.get(Document, task.document_id), 'cleanup', 'failed', code, attempt, time.time())
            return True
