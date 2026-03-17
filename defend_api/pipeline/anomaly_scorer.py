from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, TypedDict, Union

import numpy as np

from ..config import get_settings
from ..logging import get_logger
from ..models.intent import get_intent_classifier


class WarmupResult(TypedDict):
    status: Literal["warmup"]
    samples_seen: int
    scored: Literal[False]


class ScoredResult(TypedDict):
    anomaly_score: float
    flagged: bool
    distance: float


AnomalyResult = Union[WarmupResult, ScoredResult]


@dataclass(frozen=True)
class _State:
    centroid: np.ndarray
    samples_seen: int


class AnomalyScorer:
    """
    Embedding-space anomaly scorer.

    - Reuses the existing L2 SentenceTransformer embedder (MiniLM) via get_intent_classifier()
    - Scores inputs by cosine distance from an EMA "clean traffic" centroid
    - Persists centroid + samples_seen to a local file
    """

    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._lock = threading.Lock()
        self._last_persist_s: float = 0.0

        settings = get_settings()
        self._warmup_samples = int(settings.ANOMALY_WARMUP_SAMPLES)
        self._threshold = float(settings.ANOMALY_THRESHOLD)
        self._centroid_path = Path(settings.ANOMALY_CENTROID_PATH)

        self._state = self._load_state()

    def embed(self, text: str) -> np.ndarray:
        classifier = get_intent_classifier()
        return classifier.embed(text)

    def compute_distance(self, embedding: np.ndarray) -> float:
        state = self._state
        centroid = state.centroid
        denom = (np.linalg.norm(embedding) * np.linalg.norm(centroid) + 1e-8)
        cos_sim = float(np.dot(embedding, centroid) / denom)
        return float(1.0 - cos_sim)

    def update_centroid(self, embedding: np.ndarray, alpha: float = 0.001) -> None:
        with self._lock:
            state = self._state
            n = state.samples_seen
            centroid = state.centroid

            if n < self._warmup_samples:
                # Stable running mean during warmup.
                new_n = n + 1
                centroid = centroid + (embedding - centroid) / float(new_n)
            else:
                new_n = n + 1
                centroid = (1.0 - alpha) * centroid + alpha * embedding

            self._state = _State(centroid=centroid.astype(np.float32), samples_seen=new_n)

            # Throttle disk writes (best-effort). Persist at most once every ~2s.
            now = time.time()
            if now - self._last_persist_s >= 2.0:
                try:
                    self._save_state(self._state)
                    self._last_persist_s = now
                except Exception as exc:  # pragma: no cover - defensive
                    self._logger.warning("Failed to persist anomaly centroid state", extra={"error": str(exc)})

    def score(self, text: str) -> AnomalyResult:
        embedding = self.embed(text)

        # Update centroid only on non-blocked traffic. This scorer itself is risk-only;
        # caller decides whether the request should contribute to the centroid.
        self.update_centroid(embedding)

        samples_seen = self._state.samples_seen
        if samples_seen < self._warmup_samples:
            return {"status": "warmup", "samples_seen": samples_seen, "scored": False}

        distance = self.compute_distance(embedding)
        flagged = distance > self._threshold
        return {"anomaly_score": float(distance), "flagged": bool(flagged), "distance": float(distance)}

    def get_samples_seen(self) -> int:
        return self._state.samples_seen

    def _load_state(self) -> _State:
        # Default: origin-centered; warmup will move it toward observed traffic.
        default = _State(centroid=np.zeros(384, dtype=np.float32), samples_seen=0)

        try:
            path = self._centroid_path
            if not path.exists():
                return default
            data = np.load(path)
            centroid = data["centroid"].astype(np.float32)
            samples_seen = int(data["samples_seen"])
            if centroid.shape != (384,):
                return default
            return _State(centroid=centroid, samples_seen=samples_seen)
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to load anomaly centroid state; starting fresh", extra={"error": str(exc)})
            return default

    def _save_state(self, state: _State) -> None:
        path = self._centroid_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # NumPy appends ".npz" when the filename doesn't end with it.
        # Use an explicit temp name ending in ".tmp.npz" so the write/replace works on Windows.
        tmp = path.with_name(path.name + ".tmp.npz")
        np.savez(tmp, centroid=state.centroid.astype(np.float32), samples_seen=np.int64(state.samples_seen))
        tmp.replace(path)


_scorer: Optional[AnomalyScorer] = None


def get_anomaly_scorer(reset: bool = False) -> AnomalyScorer:
    global _scorer
    if reset or _scorer is None:
        _scorer = AnomalyScorer()
    return _scorer

