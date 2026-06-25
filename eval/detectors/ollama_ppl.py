"""APPROXIMATE perplexity detector via teacher-forcing on Ollama.

Idea: AI text is usually more predictable than human text, so a language model
has lower perplexity on it. We estimate perplexity with teacher-forcing:
  - walk the text by word tokens (stdlib regex);
  - at each sampled position send the prefix (everything before the token), ask
    for 1 token with top_logprobs=K;
  - find the actual next token among the top_logprobs, take its logprob
    (if it's not in the top, floor -15, i.e. "the model is very surprised");
  - average -(logprob) -> mean NLL -> perplexity = exp(mean NLL).

EXPENSIVE: dozens of HTTP calls per text (Ollama is serial). So:
  - we sample at most ~40 positions per text (uniformly by length);
  - we use a small fast model (env OLLAMA_PPL_MODEL, default gemma3:1b).
This is a nice-to-have and an APPROXIMATION OVER A SAMPLE, not honest subword
perplexity: the word tokenization != the model's tokenizer, top-K is truncated.
So the detector is NOT in the default --detectors, only behind --perplexity.

Env: OLLAMA_HOST, OLLAMA_PPL_MODEL (default gemma3:1b).
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

from .base import Detector

_EVAL_DIR = Path(__file__).resolve().parent.parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

import re

import llm_backend  # noqa: E402

# Word tokenization is done with a stdlib regex (no external NLP libs) — the
# whole project is dependency-free. The split is approximate anyway (it never
# matches the model's subword tokenizer), so a word-level regex is good enough.
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9]+(?:['’][A-Za-zÀ-ÿ]+)?|[.!?,;:]")


def ppl_model() -> str:
    return os.environ.get("OLLAMA_PPL_MODEL", "gemma3:1b")


# Sample and normalization parameters.
MAX_POSITIONS = 40        # max position-calls per text
TOP_LOGPROBS = 20         # how many candidates we request
FLOOR_LOGPROB = -15.0     # penalty if the actual token isn't in top-K
MIN_TOKENS = 6            # shorter than this — nothing to score

# Normalize to an "AI probability" via mean NLL (= log perplexity), not via raw
# perplexity: exp() on our approximate NLLs easily blows up into the millions and
# collapses the sigmoid. We work in the log domain — numerically stable.
# ai = sigmoid((NLL_CENTER - mean_nll) / NLL_SCALE): lower NLL (more predictable,
# "more AI") => higher probability. Center/scale are empirical; the word
# tokenization != the model's subwords and top-K is truncated — this is an
# APPROXIMATION, not honest perplexity.
NLL_CENTER = 6.0   # mean NLL ~6 (ppl ~400) => 0.5 on our sample
NLL_SCALE = 2.5


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _sample_indices(n: int) -> list[int]:
    """Position indices (1..n-1) to score: a uniform sample of at most MAX."""
    positions = list(range(1, n))  # position 0 has no prefix
    if len(positions) <= MAX_POSITIONS:
        return positions
    step = len(positions) / MAX_POSITIONS
    return [positions[int(i * step)] for i in range(MAX_POSITIONS)]


class OllamaPPLDetector(Detector):
    name = "ollama_ppl"

    @property
    def available(self) -> bool:
        return llm_backend.available()

    def _mean_nll(self, text: str) -> float | None:
        """Mean negative log-likelihood over the sampled positions (= log perplexity).

        This is the "raw material" for both perplexity() and score(). None when
        unavailable or the text is too short.
        """
        if not self.available:
            return None
        toks = _tokens(text)
        if len(toks) < MIN_TOKENS:
            return None

        model = ppl_model()
        nlls: list[float] = []
        for idx in _sample_indices(len(toks)):
            prefix = " ".join(toks[:idx])  # prefix before the target token
            target = toks[idx]
            resp = llm_backend.generate_with_logprobs(
                prefix,
                num_predict=1,
                top_logprobs=TOP_LOGPROBS,
                temperature=0.0,
                model=model,
            )
            logprob = FLOOR_LOGPROB
            if resp:
                lps = resp.get("logprobs") or []
                if lps:
                    cands = lps[0].get("top_logprobs") or []
                    # Find the actual next token among the candidates. The
                    # model's tokenizer (BPE subwords with a leading space) does
                    # NOT match our word tokens, so we match softly: exact match,
                    # or a candidate that is a non-empty PREFIX of the target word
                    # (the typical first subword), ignoring leading space and
                    # case. We take the logprob of the best match.
                    tgt = target.strip().lower()
                    for c in cands:
                        ctok = str(c.get("token", "")).strip().lower()
                        if not ctok:
                            continue
                        if ctok == tgt or tgt.startswith(ctok) or ctok.startswith(tgt):
                            logprob = float(c.get("logprob", FLOOR_LOGPROB))
                            break
            nlls.append(-logprob)

        if not nlls:
            return None
        return sum(nlls) / len(nlls)

    def perplexity(self, text: str) -> float | None:
        """Approximate perplexity = exp(mean NLL). None when unavailable.

        The number can be very large: the word tokens don't match the model's
        subwords, so many positions hit the floor. For normalization score()
        works in the log domain (mean NLL), not with this raw value.
        """
        mean_nll = self._mean_nll(text)
        if mean_nll is None:
            return None
        return math.exp(min(mean_nll, 50.0))

    def score(self, text: str) -> float | None:
        """Normalized "AI probability" 0..1 (lower perplexity => higher).

        Normalized in the log domain via mean NLL — robust to blown-up exp.
        """
        mean_nll = self._mean_nll(text)
        if mean_nll is None:
            return None
        z = (NLL_CENTER - mean_nll) / NLL_SCALE
        z = max(-50.0, min(50.0, z))  # guard against exp overflow
        ai = 1.0 / (1.0 + math.exp(-z))
        return max(0.0, min(1.0, ai))
