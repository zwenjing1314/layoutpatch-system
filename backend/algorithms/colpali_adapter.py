"""Read-only local ColPali adapter. No research imports, training, or HTTP service."""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import time

from PIL import Image
import torch

from .contracts import DIM, PAGE_TOKENS, PATCH_TOKENS, unpad_query, valid_embedding


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class ColPaliAdapter:
    def __init__(self, adapter_path: Path, base_path: Path, profile_path: Path,
                 device: str = "cuda:0") -> None:
        if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
            raise RuntimeError("Offline environment must be set before importing model dependencies")
        self.profile = json.loads(profile_path.read_text("utf-8"))
        self.profile_id = file_sha256(profile_path)
        self.device = device
        if device != "cpu" and (device != "cuda:0" or not torch.cuda.is_available()):
            raise ValueError("This adapter supports cpu or the available cuda:0 device")
        self.adapter_path = adapter_path.resolve(strict=True)
        self.base_path = base_path.resolve(strict=True)
        self.verified_files = []
        for label, root in (("adapter", self.adapter_path), ("base", self.base_path)):
            for name, expected in self.profile["model_files"][label].items():
                path = (root / name).resolve(strict=True)
                if not path.is_relative_to(root) or file_sha256(path) != expected:
                    raise ValueError(f"Model identity mismatch: {label}/{name}")
                self.verified_files.append(f"{label}/{name}")
        self.model = None
        self.processor = None
        self.query_calls = 0
        self.page_calls = 0
        self.query_audit: list[dict] = []
        self.load_seconds = 0.0

    def load(self) -> None:
        from colpali_engine.models import ColPali, ColPaliProcessor

        for name, cls in (("ColPali", ColPali), ("ColPaliProcessor", ColPaliProcessor)):
            actual = file_sha256(Path(inspect.getfile(cls)))
            expected = self.profile["historical_implementation_sha256"][name]
            if actual != expected:
                raise ValueError(f"Encoder implementation differs from frozen identity: {name}")
        start = time.perf_counter()
        self.processor = ColPaliProcessor.from_pretrained(str(self.adapter_path), local_files_only=True)
        # The pinned transformers version accepts an explicit local adapter directory
        # while loading the explicit local base. No adapter_config edit or remote ID resolution.
        self.model, info = ColPali.from_pretrained(
            str(self.base_path), local_files_only=True, dtype=torch.bfloat16,
            device_map=self.device, output_loading_info=True,
            adapter_kwargs={"_adapter_model_path": str(self.adapter_path), "local_files_only": True},
        )
        self.loading_info = {key: list(info.get(key, [])) for key in
                             ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")}
        if any(self.loading_info.values()):
            raise ValueError(f"Incomplete model/adapter load: {self.loading_info}")
        if not getattr(self.model, "_hf_peft_config_loaded", False):
            raise ValueError("ColPali adapter was not activated")
        self.model.eval().requires_grad_(False)
        self.load_seconds = time.perf_counter() - start

    def encode_page(self, image_path: Path) -> torch.Tensor:
        if self.model is None or self.processor is None:
            raise RuntimeError("Call load() first")
        with Image.open(image_path) as image:
            batch = self.processor.process_images([image.convert("RGB")]).to(self.device)
        image_mask = batch["input_ids"][0] == self.model.config.image_token_index
        positions = image_mask.nonzero().flatten().cpu()
        if not torch.equal(positions, torch.arange(PATCH_TOKENS)):
            raise ValueError("Expected first 1024 image tokens in row-major patch layout")
        if batch["input_ids"].shape != (1, PAGE_TOKENS) or not (batch["attention_mask"] == 1).all():
            raise ValueError("Page token layout differs from frozen profile")
        with torch.inference_mode():
            output = self.model(**batch)[0]
        self.page_calls += 1
        return valid_embedding(output, rows=PAGE_TOKENS)

    def encode_queries(self, questions: list[str]) -> list[torch.Tensor]:
        if self.model is None or self.processor is None:
            raise RuntimeError("Call load() first")
        if not questions or any(not q.strip() or len(q) > 2000 for q in questions):
            raise ValueError("Queries must be nonempty and at most 2000 characters")
        batch = self.processor.process_queries(questions).to(self.device)
        with torch.inference_mode():
            output = self.model(**batch)
        self.query_calls += 1
        result = []
        for question, embedding, mask, ids in zip(questions, output, batch["attention_mask"],
                                                  batch["input_ids"], strict=True):
            result.append(unpad_query(embedding, mask))
            self.query_audit.append({"question": question, "valid_tokens": int(mask.sum()),
                "padding_tokens": int((mask == 0).sum()),
                "valid_pad_id_tokens": int(((ids == self.processor.tokenizer.pad_token_id) & mask.bool()).sum()),
                "input_ids": ids[mask.bool()].cpu().tolist()})
        return result
