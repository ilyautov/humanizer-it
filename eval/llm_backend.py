"""Local Ollama client for the LLM evaluation layer of the humanizer-it eval harness.

The entire LLM evaluation layer: detectors, judge, faithfulness call here rather
than the cloud. No Anthropic/OpenAI keys are needed — it works against a local
Ollama daemon (`ollama serve`). If the daemon is unavailable, everything degrades
to None/False: no exceptions are propagated outward, and run_eval's metrics mode
is unaffected.

Ollama contract (verified live):
  GET  /api/tags                        — list of models (liveness check).
  POST /api/generate {model,prompt,...} — {"response": str, "logprobs": [...]}.
  POST /api/embed   {model,input}       — {"embeddings": [[float,...]]}.

Env:
  OLLAMA_HOST   — API base (default http://localhost:11434).
  OLLAMA_MODEL  — default chat model (gemma3:4b — knows Italian,
                  does not emit reasoning tags).
  OLLAMA_EMBED  — embedding model (nomic-embed-text, needed for faithfulness).

Notes on models:
  - gemma3:* answer cleanly, without <think>.
  - qwen3:* wrap reasoning in <think>...</think> — we strip it out,
    so JSON/number parsing does not break.
Ollama is serial and not fast — we set generous timeouts (120-180s).
"""

from __future__ import annotations

import json
import os
import re

# requests is an optional dependency (eval/requirements-eval.txt). Without it
# the entire Ollama layer is simply disabled, like any other external tool.
try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover — environment without requests
    requests = None  # type: ignore


def host() -> str:
    """Ollama API base without a trailing slash."""
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def default_model() -> str:
    return os.environ.get("OLLAMA_MODEL", "gemma3:4b")


def default_embed_model() -> str:
    return os.environ.get("OLLAMA_EMBED", "nomic-embed-text")


# Timeouts: tags — a quick ping; generate/embed — Ollama is serial and slow.
_TAGS_TIMEOUT_S = 5
_GEN_TIMEOUT_S = 180
_EMBED_TIMEOUT_S = 120

# Stripping reasoning tags of the form <think>...</think> (qwen3 and similar).
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    """Removes reasoning tags and collapses extra whitespace at the edges."""
    return _THINK_RE.sub("", text).strip()


def available() -> bool:
    """True if the Ollama daemon responds to /api/tags (and requests exists)."""
    if requests is None:
        return False
    try:
        resp = requests.get(f"{host()}/api/tags", timeout=_TAGS_TIMEOUT_S)
        return resp.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    """Names of available models. Empty list if Ollama is unavailable."""
    if requests is None:
        return []
    try:
        resp = requests.get(f"{host()}/api/tags", timeout=_TAGS_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def generate(
    prompt: str,
    num_predict: int = 512,
    temperature: float = 0.0,
    model: str | None = None,
) -> str | None:
    """Generate text. None if Ollama is unavailable or on error.

    temperature=0 by default — we want deterministic evaluation, not
    creativity. Reasoning tags are stripped from the response.
    """
    if requests is None:
        return None
    model = model or default_model()
    try:
        resp = requests.post(
            f"{host()}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": num_predict, "temperature": temperature},
            },
            timeout=_GEN_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        return _strip_think(data.get("response", "") or "")
    except Exception:
        return None


def _extract_json(raw: str) -> dict | None:
    """Extracts the first JSON object from the model's response.

    Removes the ```json fence, strips think tags, finds the first balanced
    {...}. None if a valid object could not be found.
    """
    if not raw:
        return None
    raw = _strip_think(raw).strip()

    # Remove the markdown fence ```json ... ```.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)

    # Direct parsing — the most common case.
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Otherwise find the first balanced {...} manually (the model may have added
    # text before/after the JSON).
    start = raw.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(raw)):
            ch = raw[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = raw[start : i + 1]
                    try:
                        obj = json.loads(chunk)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break  # this block is malformed — look for the next {
        start = raw.find("{", start + 1)
    return None


def generate_json(
    prompt: str,
    num_predict: int = 512,
    model: str | None = None,
) -> dict | None:
    """Generate and parse a JSON object. None on failure.

    A strict "valid JSON only" instruction is appended to the prompt; the
    response is parsed robustly (```json fence, think tags, first {...}).
    """
    full = (
        prompt.rstrip()
        + "\n\nReply with ONLY a valid JSON object without a markdown wrapper, "
        "explanations, or text before or after."
    )
    raw = generate(full, num_predict=num_predict, temperature=0.0, model=model)
    if raw is None:
        return None
    return _extract_json(raw)


def embed(text: str, model: str | None = None) -> list[float] | None:
    """Embedding vector of the text via /api/embed. None if unavailable."""
    if requests is None:
        return None
    model = model or default_embed_model()
    try:
        resp = requests.post(
            f"{host()}/api/embed",
            json={"model": model, "input": text},
            timeout=_EMBED_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        embs = data.get("embeddings") or []
        if embs and isinstance(embs[0], list):
            return [float(x) for x in embs[0]]
        return None
    except Exception:
        return None


def generate_with_logprobs(
    prompt: str,
    num_predict: int = 1,
    top_logprobs: int = 20,
    temperature: float = 0.0,
    model: str | None = None,
) -> dict | None:
    """Raw /api/generate response with logprobs for the generated tokens.

    Used by the perplexity detector (teacher-forcing). Returns the full JSON
    response (the fields response, logprobs, eval_count are needed). None on error.

    IMPORTANT: logprobs are returned only for the GENERATED tokens (their count
    equals eval_count), not for the prompt tokens.
    """
    if requests is None:
        return None
    model = model or default_model()
    try:
        resp = requests.post(
            f"{host()}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": num_predict, "temperature": temperature},
                "logprobs": True,
                "top_logprobs": top_logprobs,
            },
            timeout=_GEN_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None
