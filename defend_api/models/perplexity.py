from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer

from ..config import get_settings
from ..logging import get_logger


@dataclass
class PerplexityOutput:
    value: float


class PerplexityScorer:
    """
    Perplexity scorer backed by a standard Transformers GPT-2 model.

    This avoids ONNX/export complexity and simply uses PyTorch under the hood.
    All we need is a stable, scalar difficulty signal for each input.
    """

    def __init__(self, model_id: str) -> None:
        self._logger = get_logger(__name__)
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        self._model = AutoModelForCausalLM.from_pretrained(model_id)
        self._model.eval()

    def score(self, text: str) -> PerplexityOutput:
        # Minimal perplexity proxy using negative log-likelihood over tokens.
        encoded = self._tokenizer(text, return_tensors="pt")
        with np.errstate(over="ignore"):
            outputs = self._model(**encoded)
            logits = outputs.logits  # [batch, seq, vocab]
            shift_logits = logits[:, :-1, :].detach().numpy()
            shift_labels = encoded["input_ids"][:, 1:].detach().numpy()

            log_probs = shift_logits - np.log(np.exp(shift_logits).sum(axis=-1, keepdims=True))
            token_log_probs = np.take_along_axis(
                log_probs, shift_labels[..., None], axis=-1
            ).squeeze(-1)
            nll = -token_log_probs
            mean_nll = float(nll.mean())

        return PerplexityOutput(value=mean_nll)


@lru_cache(maxsize=1)
def get_perplexity_scorer() -> PerplexityScorer:
    settings = get_settings()
    # Use PERPLEXITY_MODEL_ID as the canonical HF model identifier.
    return PerplexityScorer(settings.PERPLEXITY_MODEL_ID)

