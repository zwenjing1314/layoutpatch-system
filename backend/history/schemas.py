from typing import Literal
from uuid import UUID
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from backend.search.routes import SearchHit, SearchInput


class HistorySearchInput(SearchInput):
    request_id: UUID
    k: int = Field(default=3, strict=True, ge=1, le=50)

    @field_validator('q')
    @classmethod
    def valid_unicode(cls, value):
        value.encode('utf-8')
        if any(unicodedata.category(c) == 'Cc' and c not in '\r\n\t' for c in value):
            raise ValueError('Text query required')
        return value


class HistorySummary(BaseModel):
    history_id: str
    title: str
    original_title: str
    created_at: str
    updated_at: str
    pinned_at: str | None
    version: int
    result_status: Literal['ok', 'empty']
    hit_count: int


class HistoryList(BaseModel):
    items: list[HistorySummary]
    next_offset: int | None
    scope_version: str
    limit_per_user: int


class HistoryDetail(BaseModel):
    entry: HistorySummary
    historical: Literal[True] = True
    q: str
    k: int
    search_mode: Literal['library', 'document']
    document_id: str | None
    target_available: bool | None
    profile_id: str
    index_generation: str
    scope_version: str
    current_scope_version: str
    timings_ms: dict[str, float]
    items: list[SearchHit]
    unavailable_count: int


class HistorySearchResponse(BaseModel):
    replayed: bool
    history: HistoryDetail


class HistoryUpdateInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(strict=True, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    pinned: StrictBool | None = None

    @field_validator('title')
    @classmethod
    def plain_title(cls, value):
        if value is None or any(unicodedata.category(c).startswith('C') or c in '\u2028\u2029' for c in value):
            raise ValueError('Single-line plain text required')
        return value

    @field_validator('pinned')
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError('Boolean required')
        return value

    @model_validator(mode='after')
    def nonempty_change(self):
        if not self.model_fields_set.intersection({'title', 'pinned'}):
            raise ValueError('A metadata change is required')
        return self


class HistoryDeleteInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(strict=True, ge=1)
    confirmed: StrictBool


class HistoryDeleteResponse(BaseModel):
    history_id: str
    deleted: Literal[True] = True
