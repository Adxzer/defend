from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List

import numpy as np
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

    This mirrors the GPT-2 perplexity setup: we rely on Hugging Face to load
    the model weights and avoid ONNX/export complexity.
    """

    def __init__(self, model_id: str, max_window: int = 512, stride: int = 128) -> None:
        self._logger = get_logger(__name__)
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_id)
        self._model.eval()
        self._max_window = max_window
        self._stride = stride

    def classify(self, text: str) -> DefendOutput:
        # Sliding-window over tokens to handle long inputs; we take the max
        # injection probability over all windows.
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
        for window_ids in windows:
            outputs = self._model(input_ids=window_ids)
            logits = outputs.logits.detach().numpy()
            # Assume binary classification, index 1 is "injection".
            probs = np.exp(logits) / np.exp(logits).sum(axis=-1, keepdims=True)
            inj_prob = float(probs[..., 1].max())
            max_prob = max(max_prob, inj_prob)

        is_injection = max_prob >= 0.5
        return DefendOutput(is_injection=is_injection, probability=max_prob)


@lru_cache(maxsize=1)
def get_defend_classifier() -> DefendQwenClassifier:
    settings = get_settings()
    return DefendQwenClassifier(settings.DEFEND_MODEL_ID)

