#!/usr/bin/env python3
"""Trigger-eval harness for humanizer-it: checks the skill's activation boundary.

Unlike run_eval.py (which measures the QUALITY of humanization), this harness
guards against the "pushy" skill description blurring the activation boundary:
on which requests humanizer-it SHOULD fire (should-trigger) and on which it must
stay silent (near-miss: code, English).

A light deterministic layer — no LLM, no keys, no network, runs in CI:

  1. description guard — the scope phrases ("ONLY with Italian", "Do NOT use
     for: ... code", "for English use the original humanizer") are still in
     SKILL.md. Catches drift: if someone loosens the boundary in the
     description, CI fails.
  2. request modality (it / en / code) from surface signals -> a trigger /
     no-trigger prediction. This is an honest proxy for the part of the
     invocation decision that's visible on the surface (language and modality).

The full "should the skill fire, by meaning" decision is made in production by
Claude from the description — not reproducible by a script and deliberately not
reproduced here. The description is read live from SKILL.md so the test checks
the current boundary.

Gate (exit code):
  - description guard failed                 -> exit 1 (scope boundary blurred);
  - false-activation > 0                     -> exit 1 (near-miss taken as trigger);
  - with --strict, also missed-trigger > 0   -> exit 1 (boundary "leaks").

Run:
    python eval/run_triggers.py            # this mode runs in CI
    python eval/run_triggers.py --strict   # a missed trigger is also a failure
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
DEFAULT_CORPUS = EVAL_DIR / "triggers.json"
DEFAULT_OUT = EVAL_DIR / "out"
SKILL_MD = ROOT / "SKILL.md"

# Description scope phrases: these substrings define the activation boundary. If
# any disappears from SKILL.md, the description has blurred the scope and
# trigger-eval loses meaning. We catch that deterministically, in CI, without an
# LLM. (Substrings are matched case-sensitively against the live description.)
REQUIRED_DESCRIPTION_PHRASES = [
    "ONLY",            # "Works ONLY with Italian"
    "Italian",         # binding to Italian
    "English",         # "for English use the original humanizer"
    "Do NOT use",      # explicit exclusion block
    "code",            # "Do NOT use for: ... code"
]

# Code signals for deterministic modality (outside the ``` fence).
_CODE_SIGNALS = [
    r"\bdef\s+\w+\s*\(", r"\bfunction\b", r"\bimport\s+\w", r"\bconst\s+\w",
    r"\breturn\b", r"=>", r"\bSELECT\b", r"\bFROM\b", r";\s*$", r"\{\s*$",
]

# Italian and English are both Latin script, so we can't separate them by
# alphabet (the way the Russian original separated Cyrillic from Latin). We use
# a function-word + diacritics heuristic instead. Accented vowels are a strong
# Italian tell English text almost never has.
_IT_DIACRITICS = re.compile(r"[àèéìòóùÀÈÉÌÒÓÙ]")
_IT_WORDS = re.compile(
    r"\b(?:il|lo|la|gli|le|un|una|uno|di|del|della|degli|delle|che|chi|è|sono|"
    r"per|con|non|più|anche|come|questo|questa|questi|nel|nella|sul|sulla|"
    r"testo|umanizza|umanizzare|riscrivi|rendilo|rendila|migliore|sembra|"
    r"robot|artificiale|naturale|burocratese|togli|elimina|meno|formale|"
    r"suona|fai|rendi|ma|in|italiano)\b",
    re.IGNORECASE,
)
_EN_WORDS = re.compile(
    r"\b(?:the|this|that|these|those|is|are|of|and|to|with|for|you|your|it|"
    r"sound|sounds|rewrite|humanize|text|make|makes|less|more|remove|removes|"
    r"please|paragraph|robotic|natural|leverage|leveraging)\b",
    re.IGNORECASE,
)


@dataclass
class CaseResult:
    id: str
    prompt: str
    lang: str
    category: str
    note: str
    expect_trigger: bool
    det_modality: str                 # it | en | code
    det_trigger: bool                 # deterministic-gate prediction

    @property
    def correct(self) -> bool:
        return self.det_trigger == self.expect_trigger

    @property
    def false_activation(self) -> bool:
        return self.det_trigger and not self.expect_trigger

    @property
    def missed(self) -> bool:
        return (not self.det_trigger) and self.expect_trigger

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "lang": self.lang,
            "category": self.category,
            "expect_trigger": self.expect_trigger,
            "det_modality": self.det_modality,
            "det_trigger": self.det_trigger,
            "correct": self.correct,
            "note": self.note,
        }


# --- reading the live skill description -----------------------------------


def read_skill_description(skill_md: Path = SKILL_MD) -> str:
    """Extracts the description field from the SKILL.md YAML frontmatter (live).

    The test must check the CURRENT description, not a baked-in copy — otherwise
    it can't catch drift. Supports both quoted and unquoted values.
    """
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{skill_md}: no YAML frontmatter")
    end = text.find("\n---", 3)
    front = text[3:end] if end != -1 else text
    m = re.search(r'^description:\s*(.+?)\s*$', front, re.MULTILINE)
    if not m:
        raise ValueError(f"{skill_md}: description field not found")
    val = m.group(1).strip()
    if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
        val = val[1:-1]
    return val


def check_description_guard(description: str) -> list[str]:
    """Returns the list of missing scope phrases (empty = boundary intact)."""
    return [p for p in REQUIRED_DESCRIPTION_PHRASES if p not in description]


# --- deterministic gate ---------------------------------------------------


def classify_modality(prompt: str) -> str:
    """it | en | code from surface signals.

    Code beats language: "refactor this ```python ...```" is code, even if the
    instruction is in Italian. So we detect code first (a ``` fence or >=2 code
    signals), then split Italian from English by a function-word + diacritics
    heuristic (both are Latin script, so the alphabet can't tell them apart).
    """
    if "```" in prompt:
        return "code"
    hits = sum(1 for pat in _CODE_SIGNALS if re.search(pat, prompt, re.MULTILINE))
    if hits >= 2:
        return "code"
    it = len(_IT_WORDS.findall(prompt)) + 2 * len(_IT_DIACRITICS.findall(prompt))
    en = len(_EN_WORDS.findall(prompt))
    if it == 0 and en == 0:
        return "it"  # empty/symbolic — don't punish, treat as in-scope
    return "it" if it >= en else "en"


def deterministic_trigger(prompt: str) -> tuple[str, bool]:
    """(modality, trigger prediction). We trigger only on Italian modality."""
    modality = classify_modality(prompt)
    return modality, modality == "it"


# --- main run -------------------------------------------------------------


def evaluate(corpus: Path, description: str) -> tuple[list[CaseResult], dict]:
    cases = json.loads(corpus.read_text(encoding="utf-8"))["cases"]
    results: list[CaseResult] = []
    for c in cases:
        modality, det_trig = deterministic_trigger(c["prompt"])
        results.append(CaseResult(
            id=c["id"],
            prompt=c["prompt"],
            lang=c.get("lang", modality),
            category=c.get("category", ""),
            note=c.get("note", ""),
            expect_trigger=c["expect"] == "trigger",
            det_modality=modality,
            det_trigger=det_trig,
        ))
    env = {
        "description_under_test": description,
        "description_guard_missing": check_description_guard(description),
    }
    return results, env


def stats(results: list[CaseResult]) -> dict:
    """Counters and precision/recall for the "trigger" class."""
    total = len(results)
    correct = sum(1 for r in results if r.correct)
    tp = sum(1 for r in results if r.expect_trigger and r.det_trigger)
    fp = sum(1 for r in results if r.false_activation)
    fn = sum(1 for r in results if r.missed)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "total": total, "correct": correct,
        "accuracy": correct / total if total else 1.0,
        "false_activation": fp, "missed": fn,
        "precision": precision, "recall": recall,
    }


# --- TRIGGERS.md generation -----------------------------------------------


def _yn(b: bool) -> str:
    return "✓" if b else "✗"


def render_markdown(results: list[CaseResult], env: dict) -> str:
    s = stats(results)
    L: list[str] = []
    L.append("# Trigger-eval — humanizer-it\n")
    L.append(
        "Auto-generated report (`eval/run_triggers.py`). Checks NOT the quality "
        "of humanization (that's `RESULTS.md`) but the **activation boundary**: "
        "should the skill fire on a request. A light deterministic layer with no "
        "LLM — the scope-phrase guard on the description from `SKILL.md` plus the "
        "request modality (Italian / English / code). The full \"by meaning\" "
        "decision is made in production by the assistant from the description; "
        "here we backstop the surface boundary.\n"
    )

    # --- description guard ---
    missing = env["description_guard_missing"]
    L.append("## Description guard (scope boundary)\n")
    if missing:
        L.append(
            "⚠ **Scope phrases missing from the SKILL.md description:** "
            + ", ".join(f"`{m}`" for m in missing)
            + ". The activation boundary is blurred — restore them in `description`.\n"
        )
    else:
        L.append(
            "✓ Scope phrases present (`ONLY with Italian`, `for English use the "
            "original humanizer`, `Do NOT use for: ... code`). The activation "
            "boundary in the description is intact.\n"
        )

    # --- summary ---
    n_trig = sum(1 for r in results if r.expect_trigger)
    n_no = len(results) - n_trig
    L.append("## Summary\n")
    L.append(f"- Cases: **{len(results)}** (should-trigger **{n_trig}**, "
             f"near-miss **{n_no}**).")
    L.append(f"- Gate accuracy: **{s['accuracy']*100:.0f}%** "
             f"({s['correct']}/{s['total']}); false activations "
             f"**{s['false_activation']}**, missed triggers **{s['missed']}**.")
    L.append(
        "\n> A **false activation** (a near-miss taken as a trigger) is the "
        "dangerous direction for a \"pushy\" description: the skill would reach "
        "into code or English. That's a hard CI gate. A missed trigger is a soft "
        "warning (a failure only with `--strict`).\n"
    )

    # --- case table ---
    L.append("## Cases\n")
    L.append("| id | category | expect | modality | verdict |")
    L.append("|---|---|---|---|---|")
    for r in results:
        expect = "trigger" if r.expect_trigger else "no-trigger"
        got = ("trigger" if r.det_trigger else "no-trigger") + f" {_yn(r.correct)}"
        L.append(f"| `{r.id}` | {r.category} | {expect} | {r.det_modality} | {got} |")
    L.append("")

    # --- near-miss by category ---
    L.append("## Near-miss by category (the skill must NOT reach in)\n")
    L.append("| category | cases | gate holds |")
    L.append("|---|---|---|")
    cats: dict[str, list[CaseResult]] = {}
    for r in results:
        if not r.expect_trigger:
            cats.setdefault(r.category, []).append(r)
    for cat, rs in sorted(cats.items()):
        held = sum(1 for r in rs if not r.det_trigger)
        L.append(f"| {cat} | {len(rs)} | {held}/{len(rs)} |")
    L.append("")

    L.append("---\n")
    L.append(
        "Deterministic layer: no keys, no network, no LLM — runs in CI. It checks "
        "the part of the invocation decision visible on the surface (language and "
        "modality) and that the scope boundary in the description is intact. The "
        "description is read live from `SKILL.md`."
    )
    return "\n".join(L) + "\n"


# --- CLI ------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Trigger-eval for humanizer-it: the skill activation boundary "
                    "(deterministic guard + modality)"
    )
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS,
                    help="JSON case corpus (default eval/triggers.json)")
    ap.add_argument("--strict", action="store_true",
                    help="treat missed triggers as failures too, not only false "
                         "activations")
    ap.add_argument("--skill", type=Path, default=SKILL_MD,
                    help="path to SKILL.md (source of the live description)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="output dir for triggers.json (default eval/out)")
    args = ap.parse_args()

    if not args.corpus.exists():
        print(f"[error] corpus not found: {args.corpus}", file=sys.stderr)
        return 2
    try:
        description = read_skill_description(args.skill)
    except (OSError, ValueError) as e:
        print(f"[error] could not read skill description: {e}", file=sys.stderr)
        return 2

    results, env = evaluate(args.corpus, description)
    s = stats(results)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "triggers.json").write_text(
        json.dumps({"env": env, "stats": s,
                    "cases": [r.as_dict() for r in results]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (EVAL_DIR / "TRIGGERS.md").write_text(
        render_markdown(results, env), encoding="utf-8"
    )
    print(f"[ok] triggers.json -> {args.out / 'triggers.json'}")
    print(f"[ok] TRIGGERS.md   -> {EVAL_DIR / 'TRIGGERS.md'}")
    print(f"[info] accuracy {s['accuracy']*100:.0f}% ({s['correct']}/{s['total']}), "
          f"false activations {s['false_activation']}, missed {s['missed']}")

    # --- gate ---
    failures: list[str] = []
    missing = env["description_guard_missing"]
    if missing:
        failures.append("description guard: missing scope phrases " + ", ".join(missing))
    if s["false_activation"] > 0:
        bad = [r.id for r in results if r.false_activation]
        failures.append(f"false activations on near-miss ({', '.join(bad)})")
    if args.strict and s["missed"] > 0:
        bad = [r.id for r in results if r.missed]
        failures.append(f"missed triggers, --strict ({', '.join(bad)})")

    if failures:
        print("\n[FAIL] trigger-eval:", file=sys.stderr)
        for f in failures:
            print(f"  ✗ {f}", file=sys.stderr)
        return 1
    print("[gate] ✓ scope boundary intact, no false activations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
