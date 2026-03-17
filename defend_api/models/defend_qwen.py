from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ..config import get_settings
from ..logging import get_logger


@dataclass
class DefendOutput:
    is_injection: bool
    probability: float


class DefendQwenClassifier:
    """
    Defend classifier backed by the Adaxer/defend Transformers model.

    We rely on Hugging Face Transformers to load model weights and avoid ONNX/export complexity.
    """

    def __init__(self, model_id: str, max_window: int = 512, stride: int = 128) -> None:
        self._logger = get_logger(__name__)
        # Some model repos ship a `tokenizer_config.json` with `extra_special_tokens`
        # set to a list. Recent Transformers expects a dict for model-specific
        # special tokens during tokenizer init (it calls `.keys()`), which can
        # crash at startup. Force a safe dict override.
        #
        # Note: `use_fast=False` is not viable for Qwen2 tokenizers in some repos
        # because the slow tokenizer requires a `vocab_file` that may be absent.
        self._tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            use_fast=True,
            extra_special_tokens={},
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(model_id)
        self._model.eval()
        self._max_window = max_window
        self._stride = stride

    def classify(self, text: str) -> DefendOutput:
        # Sliding-window over tokens to handle long inputs; we take the max
        # injection probability over all windows.
        settings = get_settings()
        max_input_tokens = int(getattr(settings, "DEFEND_MAX_INPUT_TOKENS", 0))
        if max_input_tokens > 0:
            encoded = self._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_input_tokens,
            )
        else:
            encoded = self._tokenizer(text, return_tensors="pt", truncation=False)
        input_ids = encoded["input_ids"]

        seq_len = input_ids.shape[1]
        windows: List[np.ndarray] = []
        start = 0
        while start < seq_len:
            end = min(start + self._max_window, seq_len)
            windows.append(input_ids[:, start:end])
            if end == seq_len:
                break
            start += self._stride

        max_prob = 0.0
        with torch.inference_mode():
            for window_ids in windows:
                outputs = self._model(input_ids=window_ids)
                logits = outputs.logits.to(dtype=torch.float32)
                probs = torch.softmax(logits, dim=-1)
                inj_prob = float(probs[..., 1].max().item())
                if np.isfinite(inj_prob):
                    max_prob = max(max_prob, inj_prob)

        # Ensure probability is finite and in [0, 1] for JSON
        max_prob = max(0.0, min(1.0, max_prob)) if np.isfinite(max_prob) else 0.0
        is_injection = max_prob >= 0.5
        return DefendOutput(is_injection=is_injection, probability=max_prob)


@lru_cache(maxsize=1)
def get_defend_classifier() -> DefendQwenClassifier:
    settings = get_settings()
    return DefendQwenClassifier(settings.DEFEND_MODEL_ID)

