"""GPTZero adapter (https://gptzero.me).

The key is taken from the GPTZERO_API_KEY environment variable. If there is no
key or the requests package is not installed — the detector is unavailable and
score() returns None. Network/HTTP errors are also swallowed into None: eval must
not crash because of an external service. requests is an optional dependency
(eval/requirements-eval.txt).
"""

from __future__ import annotations

import os

from .base import Detector

# requests is optional: import softly so a missing package does not break the import.
try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover — environment without requests
    requests = None  # type: ignore

API_URL = "https://api.gptzero.me/v2/predict/text"
TIMEOUT_S = 30


class GPTZeroDetector(Detector):
    name = "gptzero"

    def __init__(self) -> None:
        self._key = os.environ.get("GPTZERO_API_KEY", "").strip()

    @property
    def available(self) -> bool:
        return bool(self._key) and requests is not None

    def score(self, text: str) -> float | None:
        if not self.available:
            return None
        try:
            resp = requests.post(
                API_URL,
                headers={"x-api-key": self._key, "Content-Type": "application/json"},
                json={"document": text},
                timeout=TIMEOUT_S,
            )
            resp.raise_for_status()
            data = resp.json()
            # In GPTZero the probability that "the text was written by AI" lives
            # in documents[0].class_probabilities.ai (or completely_generated_prob
            # in older responses). We take it as robustly as possible.
            doc = (data.get("documents") or [{}])[0]
            probs = doc.get("class_probabilities") or {}
            if "ai" in probs:
                return float(probs["ai"])
            if "completely_generated_prob" in doc:
                return float(doc["completely_generated_prob"])
            return None
        except Exception:
            # Any error (network, limit, format) -> degrade to None.
            return None
