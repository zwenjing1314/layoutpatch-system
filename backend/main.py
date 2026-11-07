"""1B-3 authentication only; no models loaded or retrieval routes."""
from contextlib import asynccontextmanager
import time
from typing import Literal
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sqlalchemy.exc import SQLAlchemyError
from starsessions import SessionMiddleware
from backend.auth.boundary import AuthBoundary
from backend.auth.routes import router
from backend.auth.settings import AuthSettings
from backend.auth.store import SQLiteSessionStore
from backend.db.connection import make_engine


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(settings=None, clock=time.time):
    settings = settings or AuthSettings.from_environment()
    engine = make_engine(settings.database)

    @asynccontextmanager
    async def lifespan(_):
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="LayoutPatch System", version="0.2.0", lifespan=lifespan)
    app.state.engine, app.state.settings, app.state.clock = engine, settings, clock
    app.state.store = SQLiteSessionStore(engine, settings, clock)
    app.add_middleware(SessionMiddleware, store=app.state.store, lifetime=settings.absolute_seconds,
                       rolling=False, cookie_name=settings.cookie_name, cookie_path="/",
                       cookie_same_site="lax", cookie_https_only=settings.secure)
    app.add_middleware(AuthBoundary, origin=settings.origin)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        return JSONResponse({"detail": "INVALID_REQUEST"}, status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc):
        return JSONResponse({"detail": "SERVICE_UNAVAILABLE"}, status_code=503)

    @app.get("/health", response_model=HealthResponse, operation_id="get_health", tags=["system"])
    def health(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return HealthResponse()

    app.include_router(router)
    return app


app = create_app()
