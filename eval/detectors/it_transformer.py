"""Local AI-text detector for Italian, built on HuggingFace transformers.

Runs offline: loads a "human vs AI" classifier via transformers + torch. These
are heavy optional dependencies (eval/requirements-eval.txt) — not in core, not
installed in CI. If transformers/torch are missing OR the model fails to
download/load, the detector is unavailable and score() -> None.

The model is overridden via the IT_DETECTOR_MODEL environment variable. The
Italian detection line of record is DeSegMa-IT @ EVALITA 2026 (UmBERTo-based,
accuracy ~0.9458); point IT_DETECTOR_MODEL at a compatible sequence-classification
checkpoint. We guarantee nothing about quality — it's just one signal of many in
the report.
"""

from __future__ import annotations

import os

from .base import Detector

# No default model on purpose: a bare LM (e.g. UmBERTo base) is NOT a human-vs-AI
# classifier and would emit meaningless scores. The detector stays unavailable
# until IT_DETECTOR_MODEL points at a real sequence-classification checkpoint
# (DeSegMa-IT / a fine-tuned UmBERTo).
DEFAULT_MODEL = os.environ.get("IT_DETECTOR_MODEL", "").strip()

# transformers and torch are optional. Any import problem -> detector disabled.
try:
    import torch  # type: ignore  # noqa: F401
    from transformers import (  # type: ignore
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )

    _HF_AVAILABLE = True
except Exception:  # pragma: no cover — environment without torch/transformers
    _HF_AVAILABLE = False


class ItTransformerDetector(Detector):
    name = "it_transformer"

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or DEFAULT_MODEL
        self._tokenizer = None
        self._model = None
        self._load_failed = False

    def _ensure_loaded(self) -> bool:
        """Lazy model load. True if the model is ready for inference."""
        if not _HF_AVAILABLE or self._load_failed:
            return False
        if self._model is not None:
            return True
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self._model_name
            )
            self._model.train(False)  # inference mode
            return True
        except Exception:
            # No internet, model doesn't exist, out of memory, etc.
            self._load_failed = True
            return False

    @property
    def available(self) -> bool:
        # Needs both the packages AND a configured model name. The actual model
        # load is deferred to the first score() so we don't download weights for
        # nothing; with no IT_DETECTOR_MODEL set, the detector stays off.
        return _HF_AVAILABLE and bool(self._model_name) and not self._load_failed

    def score(self, text: str) -> float | None:
        if not self.available or not self._ensure_loaded():
            return None
        try:
            inputs = self._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            )
            with torch.no_grad():
                logits = self._model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0]
            # Convention: index 1 is the "AI/machine-generated" class. If the model
            # has a single logit, treat it as a sigmoid AI probability.
            if probs.shape[-1] >= 2:
                return float(probs[1].item())
            return float(torch.sigmoid(logits[0][0]).item())
        except Exception:
            return None
