"""Shape, masking and ranking rules shared by CLI and future business routes."""
from __future__ import annotations

from dataclasses import dataclass

import torch

DIM = 128
PAGE_TOKENS = 1031
PATCH_TOKENS = 1024


@dataclass(frozen=True)
class PageHit:
    page_id: str
    rank: int
    score: float


def valid_embedding(value: torch.Tensor, *, rows: int | None = None) -> torch.Tensor:
    if value.ndim != 2 or value.shape[1] != DIM or len(value) == 0:
        raise ValueError(f"Expected nonempty [T,{DIM}] embedding, got {tuple(value.shape)}")
    if rows is not None and len(value) != rows:
        raise ValueError(f"Expected {rows} tokens, got {len(value)}")
    if not torch.isfinite(value).all():
        raise ValueError("Embedding contains nonfinite values")
    if not ((value.float().norm(dim=1) - 1).abs() < 0.03).all():
        raise ValueError("Embedding contains non-unit/zero token rows")
    return value.detach().cpu().contiguous()


def unpad_query(value: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    if attention_mask.ndim != 1 or value.ndim != 2 or len(attention_mask) != len(value):
        raise ValueError("Query/mask shape mismatch")
    if not ((attention_mask == 0) | (attention_mask == 1)).all():
        raise ValueError("Attention mask must be binary")
    keep = attention_mask.bool()
    if (value[~keep] != 0).any():
        raise ValueError("Masked padding must have exactly zero embeddings")
    # Token ID 0 can also be a valid augmentation token: use attention, not IDs.
    return valid_embedding(value[keep])


def maxsim_scores(query: torch.Tensor, pages: list[torch.Tensor]) -> torch.Tensor:
    query = valid_embedding(query).float()
    if not pages:
        return torch.empty(0, dtype=torch.float32)
    return torch.stack([(query @ valid_embedding(page, rows=PAGE_TOKENS).float().T)
                        .amax(dim=1).sum() for page in pages])


def top_k(page_ids: list[str], scores: torch.Tensor, k: int) -> list[PageHit]:
    if not 1 <= k <= 50:
        raise ValueError("k must be in [1,50]")
    if scores.ndim != 1 or len(scores) != len(page_ids) or len(set(page_ids)) != len(page_ids):
        raise ValueError("Unique page IDs must match score count")
    if not torch.isfinite(scores).all():
        raise ValueError("Scores must be finite")
    order = sorted(range(len(page_ids)), key=lambda i: (-float(scores[i]), page_ids[i]))[:k]
    return [PageHit(page_ids[i], rank + 1, float(scores[i])) for rank, i in enumerate(order)]
