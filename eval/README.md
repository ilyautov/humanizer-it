# Eval harness — humanizer-it

Measures how well the `humanizer-it` skill humanizes Italian AI text, and guards
against regressions. The main artifact is [`RESULTS.md`](./RESULTS.md)
(auto-generated, referenced by the root README).

There are two independent harnesses here:

- **Quality** ([`run_eval.py`](./run_eval.py) → [`RESULTS.md`](./RESULTS.md)) —
  how well the skill cleans text (metrics, detectors, judge, faithfulness).
  Described below, the bulk of this file.
- **Activation boundary** ([`run_triggers.py`](./run_triggers.py) →
  [`TRIGGERS.md`](./TRIGGERS.md)) — on which requests the skill SHOULD fire and on
  which it must stay silent (code, English). A light deterministic layer with no
  LLM. See [Trigger-eval](#trigger-eval-the-skill-activation-boundary).

## What we measure

Three layers, by increasing cost and "semantics":

1. **Deterministic metrics** (always, no keys, no network) — the
   `scripts/humanizer_metrics` engine:
   - **HARD BANS** — 15 banned constructions (em-dash, «non solo X, ma anche Y»,
     «gioca un ruolo cruciale», «è importante notare che», «nel mondo di oggi»,
     etc.). Any hit = a failure.
   - **Markers** — 20 quick-scanner categories (burocratese, calques, inflation…).
   - **Rhythm CV** — coefficient of variation of sentence length. AI rhythm is
     flat (low CV), humans are jagged (CV ≥ 0.45). Computed by variance, not by eye.
   - **Morphosyntax** — Italian heuristics (no spaCy/pymorphy): nominalization
     density (`-zione/-mento/-ità…`, target ≤ 0.07), redundant subject pronouns
     (pro-drop violations, per-100-words), and under-used ci/ne clitics.

2. **Real detectors** (optional, `--detectors` flag) — models returning a
   "text written by AI" probability 0..1:
   - **ollama_llm** — LOCAL Ollama (default), no keys, no outbound network;
   - **GPTZero** (cloud, key `GPTZERO_API_KEY`);
   - **Originality.ai** (cloud, key `ORIGINALITY_API_KEY`);
   - **it_transformer** (local HF model, transformers + torch; point
     `IT_DETECTOR_MODEL` at an Italian AI-text classifier — DeSegMa-IT / UmBERTo);
   - **ollama_ppl** — approximate perplexity detector (`--perplexity` flag, below).

   Any unavailable detector is silently skipped (`score → None`).

3. **LLM judge** (optional, `--judge` flag) — by default LOCAL Ollama scores
   0..100 "how much this reads like living human Italian" and lists the remaining
   AI patterns. Anthropic is an option (see backends below). With neither Ollama
   nor `ANTHROPIC_API_KEY`, the judge is skipped.

4. **Faithfulness — meaning protection** (optional, `--faithfulness` flag) — so we
   don't game the metrics at the cost of content. For raw→humanized pairs it
   computes:
   - **cosine** — cosine of embeddings (Ollama model `nomic-embed-text`);
   - **meaning** — an LLM check (Ollama): are facts, numbers, key claims
     preserved; a 0..100 score + a list of what was lost/distorted;
   - **verdict**: "ok" if `cosine ≥ 0.75` and `meaning ≥ 70`, else
     "⚠ meaning degraded".

Semantics (calques, irony, translationese, voice liveliness) are caught only by
the judge — the deterministic metrics don't claim to.

### Ollama backend (local LLM layer, no cloud keys)

The LLM layer (the `ollama_llm` detector, the judge, faithfulness, perplexity)
talks to a **local Ollama** (`ollama serve`, default `http://localhost:11434`).
An Anthropic key is **not needed**. The client is
[`llm_backend.py`](./llm_backend.py): graceful — with Ollama unavailable
everything degrades to `None`/`False`, and the metrics mode is unaffected.

Setup (once):

```bash
ollama pull gemma3:4b          # default chat model (knows Italian)
ollama pull nomic-embed-text   # embeddings for faithfulness
ollama pull gemma3:1b          # fast model for --perplexity (optional)
```

> **For a meaningful detector/judge use a bigger model.** On a 4b model the
> detector tends to be blind (near-constant scores, no discrimination); a larger
> model (e.g. `OLLAMA_MODEL=gemma3:27b`) develops signal. The false-positive
> problem on formal human text is a property of the task, not the model; the
> detector is useful as a RELATIVE metric (before/after), not as a binary verdict.
> (These thresholds are still to be calibrated against an Italian A/B corpus.)

The judge picks its backend like this (`JUDGE_BACKEND`, default `auto`): Anthropic
only if `ANTHROPIC_API_KEY` is set AND the `anthropic` package is installed;
otherwise local Ollama. Every LLM section in `RESULTS.md` is tagged with which
Ollama model produced it.

**`ollama_ppl` (perplexity, `--perplexity` flag)** — teacher-forcing: walk the
text, at each sampled position request 1 token with `top_logprobs`, find the
actual next token, accumulate NLL → perplexity. Low perplexity ⇒ higher
"AI probability". It is an **approximation over a sample** (≤ 40 positions; word
tokenization ≠ the model's subwords), and expensive (dozens of calls per text).
So it is **not** part of the default `--detectors` and is enabled only by its own
flag.

## How to run

```bash
# Metrics-only (deterministic, no keys, no Ollama) — this mode runs in CI:
python eval/run_eval.py

# Full mode on LOCAL Ollama: before/after + detectors + judge + meaning protection:
python eval/run_eval.py --humanized eval/corpus/humanized \
    --detectors --judge --faithfulness

# Local LLM detector only, no judge:
python eval/run_eval.py --detectors

# Add the approximate perplexity detector (expensive, sampled):
python eval/run_eval.py --detectors --perplexity
```

The optional dependencies (requests / anthropic / transformers / torch) are in
[`requirements-eval.txt`](./requirements-eval.txt); core has none:

```bash
pip install -r eval/requirements-eval.txt
```

### Arguments

| flag | purpose |
|---|---|
| `--corpus DIR` | corpus dir with `meta.json` (default `eval/corpus`) |
| `--humanized DIR` | dir with humanized `<id>.txt` versions for the before/after comparison; without it, a raw-only baseline |
| `--detectors` | enable real detectors (`ollama_llm` on local Ollama; cloud ones if keys are present) |
| `--perplexity` | add the approximate `ollama_ppl` perplexity detector (expensive, sampled; needs Ollama) |
| `--judge` | enable the LLM judge (default local Ollama; Anthropic optional) |
| `--faithfulness` | meaning protection raw→humanized: cosine + meaning + verdict (local Ollama + `nomic-embed-text`) |
| `--out DIR` | where to write `results.json` (default `eval/out`) |
| `--baseline FILE` | regression gate: compare against a baseline, `exit 1` on a drop |
| `--save-baseline` | write the current metrics snapshot as `baseline.json` |

## Environment variables

| variable | for | default |
|---|---|---|
| `OLLAMA_HOST` | local Ollama API base | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama chat model (detector/judge/meaning) | `gemma3:4b` |
| `OLLAMA_EMBED` | Ollama embedding model (faithfulness cosine) | `nomic-embed-text` |
| `OLLAMA_PPL_MODEL` | model for the `ollama_ppl` perplexity detector | `gemma3:1b` |
| `JUDGE_BACKEND` | judge backend: `auto` / `ollama` / `anthropic` | `auto` |
| `GPTZERO_API_KEY` | GPTZero cloud detector (optional) | — |
| `ORIGINALITY_API_KEY` | Originality.ai cloud detector (optional) | — |
| `ANTHROPIC_API_KEY` | LLM judge via Anthropic (optional, NOT required) | — |
| `JUDGE_MODEL` | Anthropic judge model (if that backend is chosen) | `claude-sonnet-4-6` |
| `IT_DETECTOR_MODEL` | HF name of the local `it_transformer` detector | — |

All are optional: with neither Ollama nor keys, the harness computes the
deterministic metrics and degrades, noting in the `RESULTS.md` footer what was
unavailable. **An Anthropic key is no longer required** — the LLM layer defaults
to local Ollama.

## Corpus

`eval/corpus/meta.json` — the manifest: `{id, type, source_model, is_human, file}`.
The corpus is stratified by the matrix from the skill's classification table:

- **types**: `marketing`, `expert`, `business`, `docs`;
- **source models**: `gpt`, `claude`, `gemini`, `human`.

Three sections:

- `raw/*.txt` — marker-saturated AI texts (the skill's input). On these we check
  that the harness confidently sees AI and that the skill cleans them.
- `human/*.txt` — living human texts (**the over-correction control**: verbatim
  Italian Wikipedia excerpts, CC BY-SA — see `corpus/ATTRIBUTION.md`).
- `humanized/*.txt` — the skill's output for the matching `raw/` ids (before/after).

### Over-correction control

The skill must not "treat the healthy": on living human text it should not find
much worth editing. A separate section computes HARD BANS and markers on the
`is_human` texts. An alarm (false positive) fires if HARD BANS > 0 or markers > 5.
That's how we catch the skill/scanner over-correcting.

## Regression gate

So that changes to the skill/metrics don't silently make things worse:

```bash
# pin a baseline (after a good run):
python eval/run_eval.py --save-baseline

# check that metrics didn't drop (for CI/pre-push):
python eval/run_eval.py --baseline eval/out/baseline.json
```

The gate compares the "after" metrics (or raw, if there's no humanized) against
the baseline by id and exits 1 if, for any text, there are **more** HARD
BANS/markers or a **lower** rhythm CV (rhythm got flatter). The baseline snapshot
lives in `eval/out/` (the dir is in `.gitignore` — artifacts aren't committed).

## Trigger-eval: the skill activation boundary

A separate harness [`run_triggers.py`](./run_triggers.py) checks **NOT the
quality** of humanization but the **activation boundary**: on which requests
humanizer-it should fire (should-trigger) and on which it must stay silent
(near-miss: code, English). It's a backstop against the "pushy" skill description
causing false invocations.

The full "should the skill fire, by meaning" decision is made in production by the
assistant from the description — not reproducible by a script. So here it's a
**light deterministic layer** (no LLM, no keys, no network, runs in CI) that
backstops the surface boundary:

- **description guard** — the scope phrases (`ONLY with Italian`, `Do NOT use
  for: ... code`, `for English use the original humanizer`) are still in
  `SKILL.md`. Catches drift: if someone loosens the boundary in the description,
  CI fails.
- **modality** of the request (`it` / `en` / `code`) from surface signals →
  a trigger/no-trigger prediction. Italian and English are both Latin script, so
  they're split by a function-word + diacritics heuristic. This is an honest proxy
  for the part of the invocation decision visible on the surface.

The corpus is [`triggers.json`](./triggers.json): `{id, prompt, lang, expect,
category, note}`. The artifact is [`TRIGGERS.md`](./TRIGGERS.md) (auto-generated).

```bash
python eval/run_triggers.py            # this mode runs in CI
python eval/run_triggers.py --strict   # a missed trigger is also a failure
```

| flag | purpose |
|---|---|
| `--strict` | treat missed triggers as failures too, not only false activations |
| `--skill FILE` | path to `SKILL.md` — source of the live `description` |
| `--corpus FILE` | JSON case corpus (default `eval/triggers.json`) |

**Gate (exit code).** Hard-fails on: a scope phrase dropping out of the
description; a **false activation** on a near-miss (code/English taken as a
trigger) — the dangerous direction for a "pushy" description. A missed trigger is
by default just a warning (a failure only with `--strict`).

## Layout

```
eval/
├── README.md              — this file
├── RESULTS.md             — public quality report (run_eval.py)
├── TRIGGERS.md            — public activation-boundary report (run_triggers.py)
├── run_eval.py            — quality orchestrator (main entry)
├── run_triggers.py        — trigger-eval: activation boundary (deterministic, no LLM)
├── triggers.json          — trigger-case corpus (should-trigger + near-miss)
├── llm_backend.py         — local Ollama client (generate/json/embed/logprobs)
├── judge.py               — LLM judge (Ollama by default, Anthropic optional)
├── faithfulness.py        — meaning protection (cosine + meaning via Ollama)
├── requirements-eval.txt  — optional deps (requests + optional anthropic/transformers)
├── corpus/
│   ├── meta.json          — corpus manifest
│   ├── ATTRIBUTION.md     — sources & licenses (Wikipedia CC BY-SA, self-gen AI)
│   ├── raw/*.txt          — AI texts
│   ├── human/*.txt        — human texts (control)
│   └── humanized/*.txt    — skill output (before/after)
├── detectors/
│   ├── base.py            — Detector ABC + contract
│   ├── gptzero.py         — GPTZero adapter (cloud)
│   ├── originality.py     — Originality.ai adapter (cloud)
│   ├── it_transformer.py  — local HF detector (Italian)
│   ├── ollama_llm.py      — local LLM detector (Ollama)
│   ├── ollama_ppl.py      — approximate perplexity detector (Ollama, --perplexity)
│   └── __init__.py        — registry: available_detectors() / perplexity_detectors()
└── out/                   — results.json, baseline.json, triggers.json (gitignored)
```
