from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np
from sentence_transformers import SentenceTransformer

from ..config import get_settings
from ..logging import get_logger


IntentLabel = Literal["benign", "neutral", "suspicious"]


@dataclass
class IntentOutput:
    label: IntentLabel
    score: float


class IntentClassifier:
    def __init__(self, model_path: str) -> None:
        self._logger = get_logger(__name__)
        self._logger.info(
            "Initializing IntentClassifier with SentenceTransformer backend",
            extra={"model_path": model_path},
        )
        self._tokenizer_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        # Simple centroid placeholders; in real deployments these should be
        # persisted vectors computed from representative traffic.
        self._centroids = {
            "benign": np.zeros(384, dtype=np.float32),
            "neutral": np.ones(384, dtype=np.float32) * 0.1,
            "suspicious": np.ones(384, dtype=np.float32),
        }

    def _embed(self, text: str) -> np.ndarray:
        return self._tokenizer_model.encode([text])[0].astype(np.float32)

    def embed(self, text: str) -> np.ndarray:
        # Public embedding accessor so other layers can reuse the same loaded model.
        return self._embed(text)

    def classify(self, text: str) -> IntentOutput:
        embedding = self._embed(text)

        # Cosine similarity against precomputed centroids.
        best_label: IntentLabel = "benign"
        best_score = -1.0
        for label, centroid in self._centroids.items():
            denom = (np.linalg.norm(embedding) * np.linalg.norm(centroid) + 1e-8)
            score = float(np.dot(embedding, centroid) / denom)
            if score > best_score:
                best_score = score
                best_label = label  # type: ignore[assignment]

        return IntentOutput(label=best_label, score=best_score)


@lru_cache(maxsize=1)
def get_intent_classifier() -> IntentClassifier:
    settings = get_settings()
    return IntentClassifier(settings.INTENT_MODEL_ID)

