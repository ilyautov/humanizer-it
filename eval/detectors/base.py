"""Base contract for an AI-text detector.

A detector is an adapter over an external service (GPTZero, Originality) or a
local model (it-transformer). All of them are optional: if a key/package is
missing, the detector reports available=False and score() returns None. The
orchestrator (run_eval.py) collects only the available detectors via the registry
and degrades gracefully if there are none at all — metrics are always computed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Detector(ABC):
    """Abstract detector. Returns the probability that the text is AI (0..1)."""

    #: short name for the report (e.g. "gptzero")
    name: str = "detector"

    @property
    @abstractmethod
    def available(self) -> bool:
        """True if the detector can actually work (has a key/package/model)."""
        raise NotImplementedError

    @abstractmethod
    def score(self, text: str) -> float | None:
        """AI-generation probability 0..1. None if the detector is unavailable or failed."""
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        state = "available" if self.available else "unavailable"
        return f"<Detector {self.name}: {state}>"
