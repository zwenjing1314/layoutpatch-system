"""Authenticated retrieval. Model starts lazily in the frozen environment."""
from contextlib import asynccontextmanager
import time
import os
from typing import Literal
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sqlalchemy.exc import SQLAlchemyError
from starsessions import SessionMiddleware, get_session_handler
from backend.auth.boundary import AuthBoundary
from backend.auth.routes import router
from backend.auth.admin import router as accounts_router
from backend.auth.settings import AuthSettings
from backend.auth.store import SQLiteSessionStore
from backend.db.connection import make_engine
from backend.search.routes import router as search_router
from backend.search.worker import ModelWorker
from backend.search.qdrant import Qdrant
from backend.documents.routes import router as pages_router
from backend.documents.ingest import router as ingest_router, recover_uploads
from backend.documents.uploads import UploadSettings
from backend.documents.pipeline import IngestionRunner
from backend.documents.listing import router as listing_router
from backend.documents.sharing import router as sharing_router
from backend.documents.tasks import router as tasks_router
from backend.parsing.routes import router as parsing_router
from backend.parsing.runner import ParsingRunner, recover as recover_parsing
from backend.regions.routes import router as regions_router


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(settings=None, clock=time.time, model_worker=None, qdrant=None, upload_settings=None, ingestion_enabled=None, parsing_enabled=None):
    settings = settings or AuthSettings.from_environment()
    engine = make_engine(settings.database)

    @asynccontextmanager
    async def lifespan(_):
        try:
            recover_uploads(engine)
            recover_parsing(engine)
            if app.state.parsing_enabled:
                app.state.parsing.start()
            if app.state.ingestion_enabled:
                app.state.ingestion.start()
            yield
        finally:
            app.state.parsing.close()
            app.state.ingestion.close()
            app.state.model_worker.close()
            engine.dispose()

    app = FastAPI(title="LayoutPatch System", version="0.5.0", lifespan=lifespan)
    app.state.upload_settings = upload_settings or UploadSettings.from_environment()
    app.state.model_worker = model_worker if model_worker is not None else ModelWorker()
    app.state.qdrant = qdrant if qdrant is not None else Qdrant()
    flag = os.getenv("LAYOUTPATCH_INGEST_ENABLED", "true")
    if flag not in ("true", "false"):
        raise ValueError("LAYOUTPATCH_INGEST_ENABLED must be true or false")
    app.state.ingestion_enabled = ingestion_enabled if ingestion_enabled is not None else flag == "true"
    app.state.ingestion = IngestionRunner(engine, app.state.model_worker, app.state.qdrant)
    parse_flag = os.getenv("LAYOUTPATCH_PARSE_ENABLED", "true")
    if parse_flag not in ("true", "false"):
        raise ValueError("LAYOUTPATCH_PARSE_ENABLED must be true or false")
    app.state.parsing_enabled = parsing_enabled if parsing_enabled is not None else parse_flag == "true"
    app.state.parsing = ParsingRunner(engine)
    app.state.engine, app.state.settings, app.state.clock = engine, settings, clock
    app.state.store = SQLiteSessionStore(engine, settings, clock)
    app.add_middleware(SessionMiddleware, store=app.state.store, lifetime=settings.absolute_seconds,
                       rolling=False, cookie_name=settings.cookie_name, cookie_path="/",
                       cookie_same_site="lax", cookie_https_only=settings.secure)
    app.add_middleware(AuthBoundary, origin=settings.origin, upload_max_bytes=app.state.upload_settings.max_bytes)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        return JSONResponse({"detail": "INVALID_REQUEST"}, status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc):
        # Do not retry a session heartbeat while returning a DB failure (e.g.
        # BEGIN IMMEDIATE timeout). A second failed write would mask this 503.
        if "session_handler" in request.scope:
            get_session_handler(request).is_loaded = False
        return JSONResponse({"detail": "SERVICE_UNAVAILABLE"}, status_code=503)

    @app.get("/health", response_model=HealthResponse, operation_id="get_health", tags=["system"])
    def health(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return HealthResponse()

    app.include_router(router)
    app.include_router(accounts_router)
    app.include_router(search_router)
    app.include_router(pages_router)
    app.include_router(ingest_router)
    app.include_router(listing_router)
    app.include_router(sharing_router)
    app.include_router(tasks_router)
    app.include_router(parsing_router)
    app.include_router(regions_router)
    return app


app = create_app()
