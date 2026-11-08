"""Frozen inference definitions extracted without arithmetic changes; see SOURCE.json."""
from __future__ import annotations
import torch
from .layout import LayoutPatchD


class InputAblatedD(LayoutPatchD):
    def __init__(self, zero_input: str):
        super().__init__()
        if zero_input not in {"text", "coords"}:
            raise ValueError("only text or explicit coordinates may be ablated")
        self.zero_input = zero_input

    def forward(self, patches, layout):
        # 新字典避免改写共享页面缓存；几何权重和节点mask保持原对象。
        inputs = {**layout, self.zero_input: torch.zeros_like(layout[self.zero_input])}
        return super().forward(patches, inputs)
