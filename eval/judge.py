"""LLM judge: rates the "human quality" of Italian text.

This is the semantic layer of the eval harness — what deterministic metrics
cannot catch (calques, irony, translationese, liveliness of voice). The judge
assigns a score of 0..100 for "how much this looks like live human Italian text"
and lists the remaining AI patterns.

The default backend is LOCAL Ollama (no cloud keys). If ANTHROPIC_API_KEY is set
and the anthropic package is installed — Anthropic can be used (an option). An
Anthropic key is NO LONGER REQUIRED.

Everything is optional: if neither Ollama nor Anthropic is available, judge_text()
returns None (graceful skip), and the orchestrator simply does not show the judge
section.

Env:
    OLLAMA_MODEL      — Ollama model for the judge (default gemma3:4b).
    JUDGE_BACKEND     — "ollama" | "anthropic" | "auto" (default auto:
                        Anthropic only if a key AND the package exist; otherwise Ollama).
    ANTHROPIC_API_KEY — key, ONLY if you want the Anthropic backend.
    JUDGE_MODEL       — Anthropic model (default claude-sonnet-4-6).
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# llm_backend (local Ollama) — the judge's primary backend.
_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

import llm_backend  # noqa: E402

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

# anthropic is optional — needed only if this backend is explicitly chosen.
try:
    import anthropic  # type: ignore

    _ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover — environment without anthropic
    _ANTHROPIC_AVAILABLE = False


# Strict rubric. We ask for strict JSON so parsing is deterministic.
RUBRIC = """\
You are a strict Italian-language editor and an expert at detecting AI text.
Rate the submitted text on a scale of 0..100: how much it looks like LIVE
HUMAN Italian text (100 = indistinguishable from text written by a live native
speaker, 0 = obvious neural-network generation with bureaucratese and cliches).

Criteria that lower the score:
- bureaucratese and nominalizations ("osservazione", "realizzazione");
- cliches and calques ("è", "nel mondo moderno", "vale la pena notare");
- even rhythm (all sentences the same length), lack of live intonation;
- em dashes instead of natural punctuation;
- parallelisms "not just X, but Y", "not only X, but also Y";
- motivational cliches, inflation, false ranges "from X to Y".

Return STRICTLY JSON without a markdown wrapper, exactly this structure:
{"human_score": <int 0..100>, "remaining_patterns": [<strings>], "comment": "<brief, in English>"}
"""


@dataclass
class JudgeResult:
    human_score: int            # 0..100, higher = more human
    remaining_patterns: list[str]
    comment: str

    def as_dict(self) -> dict:
        return {
            "human_score": self.human_score,
            "remaining_patterns": self.remaining_patterns,
            "comment": self.comment,
        }


def _anthropic_ready() -> bool:
    return _ANTHROPIC_AVAILABLE and bool(
        os.environ.get("ANTHROPIC_API_KEY", "").strip()
    )


def judge_backend() -> str | None:
    """Which backend is actually available: "anthropic", "ollama" or None.

    JUDGE_BACKEND forces the choice: "anthropic" / "ollama" / "auto" (the
    default). In auto, Anthropic is used only if both a key AND the package
    exist, otherwise Ollama.
    """
    forced = os.environ.get("JUDGE_BACKEND", "auto").strip().lower()
    if forced == "anthropic":
        return "anthropic" if _anthropic_ready() else None
    if forced == "ollama":
        return "ollama" if llm_backend.available() else None
    # auto: prefer Anthropic if it is explicitly configured, otherwise Ollama.
    if _anthropic_ready():
        return "anthropic"
    if llm_backend.available():
        return "ollama"
    return None


def judge_available() -> bool:
    """True if the judge can actually work (Ollama OR Anthropic)."""
    return judge_backend() is not None


def _parse_json(raw: str) -> dict | None:
    """Extracts JSON from the model's response, even if wrapped in text/```json."""
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace:
            raw = brace.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _judge_anthropic(text: str, model: str | None) -> dict | None:
    model = model or os.environ.get("JUDGE_MODEL", DEFAULT_ANTHROPIC_MODEL)
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=RUBRIC,
            messages=[{"role": "user", "content": text}],
        )
        raw = "".join(
            block.text for block in resp.content
            if getattr(block, "type", "") == "text"
        )
    except Exception:
        return None
    return _parse_json(raw)


def _judge_ollama(text: str, model: str | None) -> dict | None:
    prompt = RUBRIC + "\n\nText to evaluate:\n---\n" + text + "\n---"
    return llm_backend.generate_json(prompt, num_predict=512, model=model)


def judge_text(text: str, model: str | None = None) -> JudgeResult | None:
    """Rates the text with the judge. None if the judge is unavailable or the call failed.

    The backend is chosen by judge_backend() (Ollama by default, Anthropic — an option).
    """
    backend = judge_backend()
    if backend is None:
        return None

    if backend == "anthropic":
        parsed = _judge_anthropic(text, model)
    else:
        parsed = _judge_ollama(text, model)

    if not parsed:
        return None

    try:
        score = int(parsed.get("human_score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    patterns = parsed.get("remaining_patterns") or []
    if not isinstance(patterns, list):
        patterns = [str(patterns)]
    return JudgeResult(
        human_score=score,
        remaining_patterns=[str(p) for p in patterns],
        comment=str(parsed.get("comment", "")),
    )
