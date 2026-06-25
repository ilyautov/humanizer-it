"""AI-text detector on local Ollama (no cloud keys).

Asks a local LLM to estimate the probability 0..1 that Italian text is
machine-generated, based on clear markers of neural-network style. Unlike the
cloud detectors (GPTZero, Originality) it requires no keys and no outbound
network — only a live Ollama daemon.

Availability = llm_backend.available(). Any call error -> score() = None.

Env (see llm_backend): OLLAMA_HOST, OLLAMA_MODEL (default gemma3:4b).
"""

from __future__ import annotations

import sys
from pathlib import Path

from .base import Detector

# llm_backend lives in eval/ (one level above detectors/). We add it to the path
# so the detector works even when the detectors package is imported directly.
_EVAL_DIR = Path(__file__).resolve().parent.parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

import llm_backend  # noqa: E402

# Rubric of AI-text markers for Italian. We ask for strictly a number + reason in JSON.
_PROMPT = """\
You are an expert at detecting machine-generated Italian text.
Estimate the probability from 0.0 to 1.0 that the text below was written by a
neural network (rather than a live human).

Markers that increase the AI probability (0.0 = clearly human, 1.0 = clearly a neural network):
- high predictability, low "perplexity" (the text flows too smoothly);
- even rhythm: sentences roughly the same length, no bursts (low burstiness);
- bureaucratese and nominalizations ("osservazione", "realizzazione");
- calques and cliches ("è", "nel mondo moderno", "vale la pena notare");
- em dashes instead of natural punctuation;
- uniform density of thought, lack of live intonation and rough edges;
- parallelisms "not just X, but Y", inflation, false ranges "from X to Y".

Text:
---
{text}
---

Return JSON in exactly this structure:
{{"ai_probability": <number 0.0..1.0>, "reason": "<brief, in English>"}}"""


class OllamaLLMDetector(Detector):
    name = "ollama_llm"

    @property
    def available(self) -> bool:
        return llm_backend.available()

    def score(self, text: str) -> float | None:
        if not self.available:
            return None
        parsed = llm_backend.generate_json(
            _PROMPT.format(text=text), num_predict=256
        )
        if not parsed:
            return None
        val = parsed.get("ai_probability")
        if val is None:
            # Sometimes the model puts the number under a different key — try softly.
            for alt in ("ai_prob", "probability", "score", "ai"):
                if alt in parsed:
                    val = parsed[alt]
                    break
        try:
            prob = float(val)
        except (TypeError, ValueError):
            return None
        # The model may have returned 0..100 instead of 0..1 — normalize.
        if prob > 1.0:
            prob = prob / 100.0
        return max(0.0, min(1.0, prob))
