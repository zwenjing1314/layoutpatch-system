"""Liveness only: no model or business routes are loaded."""
from typing import Literal
from fastapi import FastAPI, Response
from pydantic import BaseModel

app = FastAPI(title="LayoutPatch System", version="0.1.0")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@app.get("/health", response_model=HealthResponse, operation_id="get_health", tags=["system"])
def health(response: Response) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse()
