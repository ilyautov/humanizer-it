"""Meaning preservation: don't game the metrics at the cost of content.

Humanization must not distort facts for the sake of nice metrics. This module
compares the original (raw) and humanized text along two axes:

  - cosine: cosine similarity of embeddings (nomic-embed-text via Ollama);
    a rough signal of "is this even about the same thing".
  - meaning: an LLM check (Ollama) — are the facts, numbers, and key claims
    preserved; a score of 0..100 + a list of what was lost/distorted.

verdict combines both signals: cosine>=0.75 AND meaning>=70 => "ok", otherwise
"warning: meaning degraded".

Everything is graceful: without Ollama/embed the corresponding field = None, and
verdict accounts only for what was computed. No keys need to leave the machine.

Env (see llm_backend): OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_EMBED.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

import llm_backend  # noqa: E402

# Verdict thresholds.
COSINE_OK = 0.75
MEANING_OK = 70


def _cosine(a: list[float], b: list[float]) -> float | None:
    """Cosine of two vectors. None if dimensions mismatch or are zero."""
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return None
    return dot / (na * nb)


def cosine_similarity(raw: str, humanized: str) -> float | None:
    """Cosine of raw/humanized embeddings via nomic-embed-text. None is graceful."""
    ea = llm_backend.embed(raw)
    eb = llm_backend.embed(humanized)
    if ea is None or eb is None:
        return None
    cos = _cosine(ea, eb)
    return round(cos, 4) if cos is not None else None


_MEANING_PROMPT = """\
You are a meticulous fact-checking editor. You are given an ORIGINAL text and its
REWRITTEN (humanized) version. The goal of the rewrite is to change the style,
NOT to distort the meaning.

Check whether the rewritten version preserves: the facts, numbers, names, key
claims, and logic of the original text. Rate meaning preservation from 0 to 100
(100 = everything preserved exactly, 0 = meaning distorted/lost). List what was
lost or distorted (if nothing — an empty list).

ORIGINAL text:
---
{raw}
---

REWRITTEN version:
---
{humanized}
---

Return JSON in exactly this structure:
{{"meaning_score": <int 0..100>, "lost_or_distorted": [<strings>], "comment": "<brief, in English>"}}"""


def meaning_check(raw: str, humanized: str) -> dict | None:
    """LLM check of meaning preservation. None if Ollama is unavailable/failed.

    Returns {"meaning_score": int, "lost_or_distorted": [str], "comment": str}.
    """
    if not llm_backend.available():
        return None
    parsed = llm_backend.generate_json(
        _MEANING_PROMPT.format(raw=raw, humanized=humanized), num_predict=512
    )
    if not parsed:
        return None
    try:
        score = int(parsed.get("meaning_score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    lost = parsed.get("lost_or_distorted") or []
    if not isinstance(lost, list):
        lost = [str(lost)]
    return {
        "meaning_score": score,
        "lost_or_distorted": [str(x) for x in lost],
        "comment": str(parsed.get("comment", "")),
    }


def faithfulness(raw: str, humanized: str) -> dict:
    """Full meaning-preservation check for a raw/humanized pair.

    Returns a dict:
      {"cosine": float|None, "meaning": dict|None, "verdict": str}

    verdict:
      - "ok" — cosine>=0.75 and meaning>=70 (or one of the signals is
        unavailable, but the available one is within bounds);
      - "warning: meaning degraded" — the available signal is below threshold;
      - "no data" — neither cosine nor meaning could be computed.
    """
    cos = cosine_similarity(raw, humanized)
    meaning = meaning_check(raw, humanized)

    meaning_score = meaning["meaning_score"] if meaning else None

    cos_ok = cos is None or cos >= COSINE_OK
    meaning_ok = meaning_score is None or meaning_score >= MEANING_OK

    if cos is None and meaning_score is None:
        verdict = "no data"
    elif cos_ok and meaning_ok:
        verdict = "ok"
    else:
        verdict = "warning: meaning degraded"

    return {"cosine": cos, "meaning": meaning, "verdict": verdict}


def faithfulness_available() -> bool:
    """True if at least one signal (embed or meaning) can be computed."""
    return llm_backend.available()
