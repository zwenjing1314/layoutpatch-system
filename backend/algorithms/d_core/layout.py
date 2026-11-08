"""Frozen inference definitions extracted without arithmetic changes; see SOURCE.json."""
from __future__ import annotations
import torch
from torch import nn
from .correspondence import clamp_bbox, correspondence_row, scale_bbox_to_model
from .nodes import TextLayoutEncoder
from .schema import TYPE_TO_ID, canonical_layout_type
from .colpali_layout import split_page_embedding
from .fusion import SparseLocalFusionV2
TEXT_DIM = 1024


def page_layout(rows: list[dict], text: torch.Tensor) -> dict[str, torch.Tensor]:
    """调用者先按layout_id排序；每页完整候选，不按query/gold挑节点。"""
    if [r["layout_id"] for r in rows] != sorted(r["layout_id"] for r in rows):
        raise ValueError("nodes must be sorted by layout_id")
    if text.shape != (len(rows), TEXT_DIM):
        raise ValueError("text must be [M,1024]")
    coords, weights, types = [], [], []
    for r in rows:
        b = clamp_bbox(scale_bbox_to_model(r["bbox"], r["page_size"]))
        x1, y1, x2, y2 = [v / 448 for v in b]
        coords.append([x1, y1, x2, y2, x2 - x1, y2 - y1])
        weights.append(correspondence_row(r["bbox"], r["page_size"]))
        types.append(TYPE_TO_ID[canonical_layout_type(r["type"])])
    raw = torch.tensor(weights, dtype=torch.float32).reshape(len(rows), 1024).T.contiguous()
    mass = raw.sum(-1, keepdim=True)
    attn = torch.where(mass > 0, raw / mass.clamp_min(1e-12), raw)
    return {"text": text.float(), "coords": torch.tensor(coords, dtype=torch.float32).reshape(-1, 6),
            "types": torch.tensor(types, dtype=torch.long), "mask": torch.ones(len(rows), dtype=torch.bool),
            "W_raw": raw, "W_attn": attn, "cover_mass": mass}

class LayoutPatchD(nn.Module):
    """组合已有两模块；参数学习范围只有节点编码器与融合器。"""
    def __init__(self):
        super().__init__()
        self.nodes = TextLayoutEncoder(TEXT_DIM, len(TYPE_TO_ID))
        self.fusion = SparseLocalFusionV2(top_k=4)

    def forward(self, patches: torch.Tensor, layout: dict[str, torch.Tensor]) -> torch.Tensor:
        nodes = self.nodes(layout["text"][None], layout["coords"][None], layout["types"][None], layout["mask"][None])
        return self.fusion(patches[None], layout["W_attn"][None], nodes, layout["cover_mass"][None],
                           node_mask=layout["mask"][None])[0]

    def forward_page(self, page: torch.Tensor, layout: dict[str, torch.Tensor]) -> torch.Tensor:
        patches, prompt = split_page_embedding(page)
        return torch.cat((self(patches, layout), prompt), dim=0)
