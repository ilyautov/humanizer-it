"""Originality.ai adapter (https://originality.ai).

The key comes from the ORIGINALITY_API_KEY environment variable. Without a key or
without the requests package the detector is unavailable, score() -> None.
Network/HTTP errors are swallowed into None. requests is an optional dependency
(eval/requirements-eval.txt).
"""

from __future__ import annotations

import os

from .base import Detector

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

API_URL = "https://api.originality.ai/api/v1/scan/ai"
TIMEOUT_S = 30


class OriginalityDetector(Detector):
    name = "originality"

    def __init__(self) -> None:
        self._key = os.environ.get("ORIGINALITY_API_KEY", "").strip()

    @property
    def available(self) -> bool:
        return bool(self._key) and requests is not None

    def score(self, text: str) -> float | None:
        if not self.available:
            return None
        try:
            resp = requests.post(
                API_URL,
                headers={"X-OAI-API-KEY": self._key, "Content-Type": "application/json"},
                json={"content": text},
                timeout=TIMEOUT_S,
            )
            resp.raise_for_status()
            data = resp.json()
            # Originality returns score.ai in the 0..1 range — the AI probability.
            score = (data.get("score") or {}).get("ai")
            if score is None:
                return None
            return float(score)
        except Exception:
            return None
