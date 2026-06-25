"""AI-text detector registry.

All detectors are optional and degrade to available=False when a key, package,
model, or live Ollama daemon is missing. available_detectors() instantiates every
known adapter and returns only the ones that can actually run right now.

ollama_ppl (perplexity over a sample) is deliberately NOT in the default set — it
is expensive and approximate, and is enabled separately via perplexity_detectors()
(the --perplexity flag in run_eval).
"""

from __future__ import annotations

from .base import Detector
from .gptzero import GPTZeroDetector
from .it_transformer import ItTransformerDetector
from .ollama_llm import OllamaLLMDetector
from .ollama_ppl import OllamaPPLDetector
from .originality import OriginalityDetector

__all__ = [
    "Detector",
    "GPTZeroDetector",
    "ItTransformerDetector",
    "OllamaLLMDetector",
    "OllamaPPLDetector",
    "OriginalityDetector",
    "all_detectors",
    "available_detectors",
    "perplexity_detectors",
]


def all_detectors() -> list[Detector]:
    """All "regular" detectors regardless of availability (for diagnostics).

    ollama_ppl is NOT here — it is expensive and enabled by a separate flag.
    """
    return [
        GPTZeroDetector(),
        OriginalityDetector(),
        ItTransformerDetector(),
        OllamaLLMDetector(),
    ]


def available_detectors() -> list[Detector]:
    """Only the detectors that can actually run in the current environment.

    ollama_llm is picked up automatically when the Ollama daemon is alive.
    """
    return [d for d in all_detectors() if d.available]


def perplexity_detectors() -> list[Detector]:
    """The expensive approximate perplexity detector (the --perplexity flag).

    Returns [OllamaPPLDetector] if available (Ollama up), otherwise [].
    """
    ppl = OllamaPPLDetector()
    return [ppl] if ppl.available else []
