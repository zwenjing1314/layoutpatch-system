"""Frozen inference definitions extracted without arithmetic changes; see SOURCE.json."""
from __future__ import annotations
import math
from collections.abc import Sequence
import torch
from torch.nn.functional import normalize
from .correspondence import GRID, clamp_bbox, patch_bbox, scale_bbox_to_model
_CELLS = torch.tensor([patch_bbox(i) for i in range(GRID * GRID)], dtype=torch.float32)


def valid_query(query: torch.Tensor) -> torch.Tensor:
    """Float32, L2-normalized query rows; all-zero (masked padding) rows are dropped."""
    q = query.float()
    keep = q.norm(dim=-1) > 1e-6
    if not bool(keep.any()):
        raise ValueError("query has no nonzero token rows")
    return normalize(q[keep], dim=-1)

def patch_scores(query: torch.Tensor, patches: torch.Tensor) -> torch.Tensor:
    """Per-patch MaxSim term over valid query tokens; ``patches`` is [1024, D]."""
    if patches.shape[0] != GRID * GRID:
        raise ValueError(f"expected {GRID * GRID} patch rows, got {tuple(patches.shape)}")
    return (valid_query(query) @ normalize(patches.float(), dim=-1).T).amax(dim=0)

def patch_iou_matrix(boxes: Sequence[Sequence[float]], page_size: Sequence[float]) -> torch.Tensor:
    """IoU between each candidate (page frame) and each 14px model patch: [M, 1024]."""
    if not boxes:
        return torch.zeros(0, GRID * GRID)
    size = [float(v) for v in page_size]
    scaled = torch.tensor(
        [clamp_bbox(scale_bbox_to_model([float(v) for v in b], size)) for b in boxes],
        dtype=torch.float32,
    )
    c = _CELLS
    w = (torch.minimum(scaled[:, None, 2], c[None, :, 2]) - torch.maximum(scaled[:, None, 0], c[None, :, 0])).clamp_min(0)
    h = (torch.minimum(scaled[:, None, 3], c[None, :, 3]) - torch.maximum(scaled[:, None, 1], c[None, :, 1])).clamp_min(0)
    inter = w * h
    box_area = ((scaled[:, 2] - scaled[:, 0]) * (scaled[:, 3] - scaled[:, 1])).clamp_min(0)
    cell_area = (c[:, 2] - c[:, 0]) * (c[:, 3] - c[:, 1])
    union = box_area[:, None] + cell_area[None, :] - inter
    return torch.where(union > 0, inter / union.clamp_min(1e-9), torch.zeros_like(inter))

def region_scores(scores: torch.Tensor, iou: torch.Tensor) -> torch.Tensor:
    """IoU-normalized patch mean per candidate; candidates touching no patch get -inf."""
    mass = iou.sum(dim=-1)
    mean = (iou @ scores) / mass.clamp_min(1e-12)
    return torch.where(mass > 0, mean, torch.full_like(mean, -math.inf))
