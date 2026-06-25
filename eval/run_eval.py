#!/usr/bin/env python3
"""Orchestrator for the humanizer-it eval harness.

What it does:
  1. Loads the stratified corpus (eval/corpus/meta.json).
  2. For each text, computes deterministic metrics (humanizer_metrics.analyze).
  3. If --humanized DIR is given, computes metrics for the humanized version with
     the same id and prints deltas (hard_ban_count, marker_count, cv_len, nominal_ratio, em_dash).
  4. If --detectors and detectors are available, runs score() before/after.
  5. If --judge and a judge is available, rates "humanness" before/after.
  6. Computes the over-correction control: on is_human texts the count of
     markers/bans must be LOW (the skill should not want to heavily edit them).
  7. Writes eval/out/results.json and a human-readable eval/RESULTS.md.

Regression gate:
  --save-baseline   record current metrics as the baseline (eval/out/baseline.json).
  --baseline FILE   compare "after" metrics against the baseline; exit 1 if they
                    regressed (more HARD BANS / markers or lower cv_len).

Without --detectors/--judge the harness is fully deterministic, requires no keys
and no network — this mode runs in CI. Usage:
    python eval/run_eval.py
    python eval/run_eval.py --humanized eval/humanized --detectors --judge
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Access to humanizer_metrics: the package lives inside the skill (ships with the install).
EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
sys.path.insert(0, str(ROOT / "skills" / "humanizer-it" / "scripts"))

from humanizer_metrics import Report, analyze  # noqa: E402

# Detectors, judge, faithfulness, Ollama backend — local optional modules.
sys.path.insert(0, str(EVAL_DIR))
import llm_backend  # noqa: E402
from detectors import available_detectors, perplexity_detectors  # noqa: E402
from faithfulness import faithfulness, faithfulness_available  # noqa: E402
from judge import judge_available, judge_backend, judge_text  # noqa: E402

DEFAULT_CORPUS = EVAL_DIR / "corpus"
DEFAULT_OUT = EVAL_DIR / "out"

# "Over-correction" threshold: on lively human text the skill should not find
# many markers. We treat it as alarming if bans > 0 or markers > 5.
HUMAN_HARD_BAN_LIMIT = 0
HUMAN_MARKER_LIMIT = 5

# Threshold at which a detector "accuses" a text of machine origin.
# If a detector gives a known-human text a score >= this, it is a false
# positive.
DETECTOR_AI_THRESHOLD = 0.5


# --- report data models ---------------------------------------------------


@dataclass
class ItemResult:
    id: str
    type: str
    source_model: str
    is_human: bool
    before: dict                       # analyze().as_dict() for raw
    after: dict | None = None          # for humanized, if present
    deltas: dict | None = None         # before -> after on key metrics
    detectors_before: dict = field(default_factory=dict)  # name -> score|None
    detectors_after: dict = field(default_factory=dict)
    judge_before: dict | None = None
    judge_after: dict | None = None
    faithfulness: dict | None = None  # cosine + meaning + verdict for the raw/after pair

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "source_model": self.source_model,
            "is_human": self.is_human,
            "before": self.before,
            "after": self.after,
            "deltas": self.deltas,
            "detectors_before": self.detectors_before,
            "detectors_after": self.detectors_after,
            "judge_before": self.judge_before,
            "judge_after": self.judge_after,
            "faithfulness": self.faithfulness,
        }


# --- utilities ------------------------------------------------------------


def _load_meta(corpus_dir: Path) -> list[dict]:
    meta_path = corpus_dir / "meta.json"
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    return data["items"]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _compute_deltas(before: dict, after: dict) -> dict:
    """Key deltas after - before. For bans/markers/dashes we want a decrease
    (negative delta = good), for cv_len an increase (positive = good)."""
    b_rhythm, a_rhythm = before["rhythm"], after["rhythm"]
    b_morph, a_morph = before["morph"], after["morph"]
    return {
        "hard_ban_count": after["hard_ban_count"] - before["hard_ban_count"],
        "marker_count": after["marker_count"] - before["marker_count"],
        "em_dash": a_rhythm["em_dash"] - b_rhythm["em_dash"],
        "cv_len": round(a_rhythm["cv_len"] - b_rhythm["cv_len"], 3),
        "nominal_ratio": round(
            a_morph["nominal_ratio"] - b_morph["nominal_ratio"], 3
        ),
    }


def _run_detectors(detectors, text: str) -> dict:
    """name -> score(0..1)|None for each available detector."""
    out = {}
    for d in detectors:
        out[d.name] = d.score(text)
    return out


def _verdict_for(rep_dict: dict) -> str:
    """Short verdict based on the deterministic metrics of one text."""
    bans = rep_dict["hard_ban_count"]
    markers = rep_dict["marker_count"]
    cv = rep_dict["rhythm"]["cv_len"]
    nv = rep_dict["morph"]["nominal_ratio"]
    if bans == 0 and markers <= 2 and cv >= 0.45 and nv <= 0.07:
        return "clean"
    if bans > 0 or markers >= 6:
        return "AI"
    return "suspicious"


# --- main run -------------------------------------------------------------


def evaluate(
    corpus_dir: Path,
    humanized_dir: Path | None,
    use_detectors: bool,
    use_judge: bool,
    use_perplexity: bool = False,
    use_faithfulness: bool = False,
) -> tuple[list[ItemResult], dict]:
    items = _load_meta(corpus_dir)
    detectors = available_detectors() if use_detectors else []
    # the perplexity detector is expensive and approximate — behind its own flag.
    if use_perplexity:
        detectors = detectors + perplexity_detectors()
    judge_on = use_judge and judge_available()
    faith_on = use_faithfulness and faithfulness_available()

    results: list[ItemResult] = []
    for it in items:
        raw_path = corpus_dir / it["file"]
        raw_text = _read_text(raw_path)
        before = analyze(raw_text).as_dict()

        res = ItemResult(
            id=it["id"],
            type=it["type"],
            source_model=it["source_model"],
            is_human=it["is_human"],
            before=before,
        )

        # humanized version with the same id (any .txt extension).
        if humanized_dir is not None:
            cand = humanized_dir / f"{it['id']}.txt"
            if cand.exists():
                after_text = _read_text(cand)
                res.after = analyze(after_text).as_dict()
                res.deltas = _compute_deltas(res.before, res.after)

        if detectors:
            res.detectors_before = _run_detectors(detectors, raw_text)
            if res.after is not None:
                after_text = _read_text(humanized_dir / f"{it['id']}.txt")
                res.detectors_after = _run_detectors(detectors, after_text)

        if judge_on:
            jb = judge_text(raw_text)
            res.judge_before = jb.as_dict() if jb else None
            if res.after is not None:
                after_text = _read_text(humanized_dir / f"{it['id']}.txt")
                ja = judge_text(after_text)
                res.judge_after = ja.as_dict() if ja else None

        # faithfulness is computed only for raw/humanized pairs (both versions needed).
        if faith_on and res.after is not None:
            after_text = _read_text(humanized_dir / f"{it['id']}.txt")
            res.faithfulness = faithfulness(raw_text, after_text)

        results.append(res)

    env = {
        "detectors_available": [d.name for d in detectors],
        "detectors_requested": use_detectors,
        "perplexity_requested": use_perplexity,
        "judge_available": judge_on,
        "judge_requested": use_judge,
        "judge_backend": judge_backend() if judge_on else None,
        "faithfulness_available": faith_on,
        "faithfulness_requested": use_faithfulness,
        "has_humanized": humanized_dir is not None,
        # Which Ollama model produced the LLM sections (for attribution in the report).
        "ollama_available": llm_backend.available(),
        "ollama_model": llm_backend.default_model(),
        "ollama_embed": llm_backend.default_embed_model(),
        "ollama_ppl_model": None,
    }
    if use_perplexity:
        # The perplexity model name — from the same env the detector uses.
        import os as _os

        env["ollama_ppl_model"] = _os.environ.get("OLLAMA_PPL_MODEL", "gemma3:1b")
    return results, env


# --- RESULTS.md generation ------------------------------------------------


def _fmt_score(v: float | None) -> str:
    return f"{v:.2f}" if isinstance(v, (int, float)) else "—"


def _fmt_delta(v: float | int, good_when_negative: bool = True) -> str:
    """Formats a delta with an arrow indicating quality direction."""
    if v == 0:
        return "0"
    sign = "+" if v > 0 else ""
    improved = (v < 0) if good_when_negative else (v > 0)
    arrow = "✓" if improved else "✗"
    return f"{sign}{v} {arrow}"


def render_markdown(results: list[ItemResult], env: dict) -> str:
    lines: list[str] = []
    lines.append("# humanizer-it eval harness results\n")
    lines.append(
        "Auto-generated report (`eval/run_eval.py`). Deterministic metrics are "
        "always computed; real detectors and the LLM judge are optional (see footer).\n"
    )

    ai_items = [r for r in results if not r.is_human]
    # The "literary" fixtures (the Tolstoy test) are deliberate false-positive
    # stress cases, not the lively-human over-correction control — they get their
    # own analysis in eval/CALIBRATION.md, so keep them out of this table.
    human_items = [r for r in results if r.is_human and r.type != "literary"]
    has_after = any(r.after is not None for r in results)
    has_detectors = bool(env["detectors_available"])
    has_judge = env["judge_available"]

    # --- Summary ---
    lines.append("## Summary\n")
    avg_bans = (
        sum(r.before["hard_ban_count"] for r in ai_items) / len(ai_items)
        if ai_items else 0
    )
    avg_markers = (
        sum(r.before["marker_count"] for r in ai_items) / len(ai_items)
        if ai_items else 0
    )
    avg_cv = (
        sum(r.before["rhythm"]["cv_len"] for r in ai_items) / len(ai_items)
        if ai_items else 0
    )
    lines.append(f"- AI texts in the corpus: **{len(ai_items)}**, human: **{len(human_items)}**")
    lines.append(f"- Average over AI texts (raw): HARD BANS **{avg_bans:.1f}**, "
                 f"markers **{avg_markers:.1f}**, rhythm CV **{avg_cv:.3f}**")
    if has_after:
        improved = sum(
            1 for r in ai_items
            if r.deltas and r.deltas["hard_ban_count"] <= 0 and r.deltas["marker_count"] < 0
        )
        lines.append(f"- Humanized versions: present; reduced markers/bans "
                     f"in **{improved}/{len(ai_items)}** AI texts")
    else:
        lines.append("- No humanized versions: only the baseline (raw) is shown.")
    lines.append("")

    # --- Table of AI texts ---
    lines.append("## AI texts (skill input)\n")
    header = "| id | type | model | HARD BANS | markers | CV | nominal | dashes | verdict |"
    sep = "|---|---|---|---|---|---|---|---|---|"
    if has_after:
        header = ("| id | type | model | bans (before→Δ) | markers (before→Δ) | "
                  "CV (before→Δ) | nominal (before→Δ) | dashes (before→Δ) | verdict after |")
        sep = "|---|---|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for r in ai_items:
        b = r.before
        if has_after and r.after is not None:
            a, d = r.after, r.deltas
            lines.append(
                f"| `{r.id}` | {r.type} | {r.source_model} "
                f"| {b['hard_ban_count']}→{_fmt_delta(d['hard_ban_count'])} "
                f"| {b['marker_count']}→{_fmt_delta(d['marker_count'])} "
                f"| {b['rhythm']['cv_len']}→{_fmt_delta(d['cv_len'], good_when_negative=False)} "
                f"| {b['morph']['nominal_ratio']}→{_fmt_delta(d['nominal_ratio'])} "
                f"| {b['rhythm']['em_dash']}→{_fmt_delta(d['em_dash'])} "
                f"| {_verdict_for(a)} |"
            )
        else:
            lines.append(
                f"| `{r.id}` | {r.type} | {r.source_model} "
                f"| {b['hard_ban_count']} | {b['marker_count']} "
                f"| {b['rhythm']['cv_len']} | {b['morph']['nominal_ratio']} "
                f"| {b['rhythm']['em_dash']} | {_verdict_for(b)} |"
            )
    lines.append("")

    # --- Detectors ---
    if has_detectors:
        lines.append("## Real detectors (AI probability, 0..1)\n")
        det_names = env["detectors_available"]
        if "ollama_llm" in det_names or "ollama_ppl" in det_names:
            note = f"Ollama detectors produced by model `{env.get('ollama_model')}`"
            if "ollama_ppl" in det_names and env.get("ollama_ppl_model"):
                note += (f"; perplexity (`ollama_ppl`) — approximate, on a sample, "
                         f"model `{env['ollama_ppl_model']}`")
            lines.append(note + ".\n")
        head = "| id | " + " | ".join(det_names) + " |"
        if has_after:
            head = "| id | " + " | ".join(f"{n} (before→after)" for n in det_names) + " |"
        lines.append(head)
        lines.append("|---|" + "|".join(["---"] * len(det_names)) + "|")
        for r in ai_items:
            cells = []
            for n in det_names:
                bsc = _fmt_score(r.detectors_before.get(n))
                if has_after:
                    asc = _fmt_score(r.detectors_after.get(n))
                    cells.append(f"{bsc}→{asc}")
                else:
                    cells.append(bsc)
            lines.append(f"| `{r.id}` | " + " | ".join(cells) + " |")
        lines.append("")

        # --- FP audit: the same detectors on KNOWN-human texts ---
        if human_items:
            det_names = env["detectors_available"]
            lines.append("## Detector FP audit (known-human texts)\n")
            lines.append(
                "The same detectors run against the \"human\" control (verbatim excerpts "
                "from Wikipedia articles, CC BY-SA — definitely not AI). If a detector gives "
                f"a score >= {DETECTOR_AI_THRESHOLD:.2f}, it **falsely accuses a human** "
                "(false positive).\n"
            )
            head = "| id | source | " + " | ".join(det_names) + " | verdict |"
            lines.append(head)
            lines.append("|---|---|" + "|".join(["---"] * len(det_names)) + "|---|")
            fp_total = 0
            fp_possible = 0
            for r in human_items:
                cells = []
                flagged_here = False
                for n in det_names:
                    sc = r.detectors_before.get(n)
                    cells.append(_fmt_score(sc))
                    if isinstance(sc, (int, float)):
                        fp_possible += 1
                        if sc >= DETECTOR_AI_THRESHOLD:
                            fp_total += 1
                            flagged_here = True
                verdict = "⚠ flagged as AI" if flagged_here else "✓ recognized as human"
                lines.append(
                    f"| `{r.id}` | {r.source_model} | " + " | ".join(cells)
                    + f" | {verdict} |"
                )
            lines.append("")
            if fp_possible:
                rate = 100.0 * fp_total / fp_possible
                lines.append(
                    f"**False positive rate: {fp_total}/{fp_possible} "
                    f"({rate:.0f}%)** of detector scores on human text — "
                    "false accusations of machine generation. This is an empirical "
                    "illustration of why binary \"human/AI\" classification in "
                    "Italian is unreliable: formal human text is routinely "
                    "mistaken for a neural network by the detector."
                )
            lines.append("")

    # --- Judge ---
    if has_judge:
        lines.append("## LLM judge \"humanness\" (0..100, higher = livelier)\n")
        jb_backend = env.get("judge_backend")
        if jb_backend == "ollama":
            lines.append(f"Produced by local Ollama, model `{env.get('ollama_model')}`.\n")
        elif jb_backend == "anthropic":
            lines.append("Produced via the Anthropic API.\n")
        lines.append("| id | before | after | remaining patterns (after) |")
        lines.append("|---|---|---|---|")
        for r in ai_items:
            jb = r.judge_before["human_score"] if r.judge_before else "—"
            ja = r.judge_after["human_score"] if r.judge_after else "—"
            patt = ""
            if r.judge_after and r.judge_after.get("remaining_patterns"):
                patt = ", ".join(r.judge_after["remaining_patterns"][:4])
            lines.append(f"| `{r.id}` | {jb} | {ja} | {patt} |")
        lines.append("")

    # --- Faithfulness (meaning preservation) ---
    has_faith = env.get("faithfulness_available") and any(
        r.faithfulness for r in ai_items
    )
    if has_faith:
        lines.append("## Faithfulness — meaning preservation (raw → humanized)\n")
        lines.append(
            f"Embedding cosine (`{env.get('ollama_embed')}`) and an LLM check of "
            f"fact preservation (`{env.get('ollama_model')}`). "
            f"Verdict \"ok\" if cosine >= 0.75 and meaning >= 70.\n"
        )
        lines.append("| id | cosine | meaning (0-100) | verdict | lost/distorted |")
        lines.append("|---|---|---|---|---|")
        for r in ai_items:
            f = r.faithfulness
            if not f:
                continue
            cos = _fmt_score(f.get("cosine"))
            meaning = f.get("meaning")
            mscore = meaning["meaning_score"] if meaning else "—"
            lost = ""
            if meaning and meaning.get("lost_or_distorted"):
                lost = "; ".join(meaning["lost_or_distorted"][:3])
            lines.append(
                f"| `{r.id}` | {cos} | {mscore} | {f.get('verdict', '—')} | {lost} |"
            )
        lines.append("")

    # --- Over-correction control ---
    lines.append("## Over-correction control (human texts)\n")
    lines.append(
        "The skill should NOT want to heavily edit lively human text. "
        f"Alarm if HARD BANS > {HUMAN_HARD_BAN_LIMIT} or markers > {HUMAN_MARKER_LIMIT}.\n"
    )
    lines.append("| id | type | HARD BANS | markers | CV | nominal | dashes | status |")
    lines.append("|---|---|---|---|---|---|---|---|")
    overzealous = 0
    for r in human_items:
        b = r.before
        bans = b["hard_ban_count"]
        markers = b["marker_count"]
        flagged = bans > HUMAN_HARD_BAN_LIMIT or markers > HUMAN_MARKER_LIMIT
        if flagged:
            overzealous += 1
        status = "⚠ false alarm" if flagged else "✓ ok"
        lines.append(
            f"| `{r.id}` | {r.type} | {bans} | {markers} "
            f"| {b['rhythm']['cv_len']} | {b['morph']['nominal_ratio']} "
            f"| {b['rhythm']['em_dash']} | {status} |"
        )
    lines.append("")
    if human_items:
        lines.append(
            f"Control result: **{len(human_items) - overzealous}/{len(human_items)}** "
            f"human texts passed clean."
        )
        if overzealous:
            lines.append("")
            lines.append(
                "> **How to read this.** The control is verbatim excerpts from "
                "Wikipedia articles (definitely human, but a **formal** register). "
                "Flags here are not a bug but the same trap that AI detectors fall "
                "into (see the FP audit above): formal human text is hard to "
                "distinguish from machine text by surface signals. Specifically, "
                "alarms come from (1) em dashes \"—\" — Wikipedia uses them "
                "routinely, but the skill bans them as a marker under a strict "
                "policy; (2) high nominal — this is encyclopedic style, not a "
                "neural network. The conclusion is honest in both directions: "
                "neither a detector nor simple heuristics deliver a reliable "
                "\"human/AI\" verdict on formal text. That is why the skill does not "
                "detect but **rewrites** — and targets a lively register, not an "
                "encyclopedic one."
            )
    lines.append("")

    # --- Availability footer ---
    lines.append("---\n")
    lines.append("### Tool availability in this run\n")
    det = env["detectors_available"]
    ollama_state = "up" if env.get("ollama_available") else "unavailable"
    lines.append(f"- Local Ollama: {ollama_state} "
                 f"(chat model `{env.get('ollama_model')}`, embed `{env.get('ollama_embed')}`)")
    lines.append(f"- Detectors requested: {'yes' if env['detectors_requested'] else 'no'}; "
                 f"available: {', '.join(det) if det else '— (no keys/packages/Ollama)'}")
    if env.get("perplexity_requested"):
        ppl_on = "ollama_ppl" in det
        lines.append(f"  - perplexity (`--perplexity`): "
                     f"{'enabled, model `' + str(env.get('ollama_ppl_model')) + '` (approximate, on a sample)' if ppl_on else 'unavailable (no Ollama)'}")
    jb_backend = env.get("judge_backend")
    jb_desc = {
        "ollama": f"Ollama (`{env.get('ollama_model')}`)",
        "anthropic": "Anthropic API",
    }.get(jb_backend, "— (no Ollama and no ANTHROPIC_API_KEY)")
    lines.append(f"- LLM judge requested: {'yes' if env['judge_requested'] else 'no'}; "
                 f"backend: {jb_desc}")
    if env.get("faithfulness_requested"):
        f_on = env.get("faithfulness_available")
        lines.append(f"- Faithfulness (`--faithfulness`): "
                     f"{'available (embed `' + str(env.get('ollama_embed')) + '` + meaning `' + str(env.get('ollama_model')) + '`)' if f_on else 'unavailable (no Ollama)'}")
    lines.append(f"- Humanized versions: {'present' if env['has_humanized'] else 'none (baseline mode)'}")
    lines.append("\nDeterministic metrics (HARD BANS, markers, rhythm CV, nominal) "
                 "are always computed and do not depend on keys, Ollama, or the network. "
                 "The LLM layer (Ollama detectors, judge, faithfulness) runs on LOCAL "
                 "Ollama — no Anthropic key required.")
    return "\n".join(lines) + "\n"


# --- regression gate ------------------------------------------------------


def _metric_snapshot(results: list[ItemResult]) -> dict:
    """Snapshot of key "after" metrics (or raw if no humanized) keyed by id."""
    snap = {}
    for r in results:
        src = r.after if r.after is not None else r.before
        snap[r.id] = {
            "hard_ban_count": src["hard_ban_count"],
            "marker_count": src["marker_count"],
            "cv_len": src["rhythm"]["cv_len"],
        }
    return snap


def check_regression(results: list[ItemResult], baseline_path: Path) -> list[str]:
    """Compares the current snapshot against the baseline. Returns a list of regressions."""
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = _metric_snapshot(results)
    regressions: list[str] = []
    for item_id, base in baseline.items():
        cur = current.get(item_id)
        if cur is None:
            continue  # text disappeared from the corpus — not a metric regression
        if cur["hard_ban_count"] > base["hard_ban_count"]:
            regressions.append(
                f"{item_id}: HARD BANS {base['hard_ban_count']} → {cur['hard_ban_count']}"
            )
        if cur["marker_count"] > base["marker_count"]:
            regressions.append(
                f"{item_id}: markers {base['marker_count']} → {cur['marker_count']}"
            )
        if cur["cv_len"] < base["cv_len"]:
            regressions.append(
                f"{item_id}: rhythm CV {base['cv_len']} → {cur['cv_len']} (flatter)"
            )
    return regressions


# --- CLI ------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description="humanizer-it eval harness: metrics + optional detectors + optional LLM judge"
    )
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS,
                    help="corpus directory (with meta.json)")
    ap.add_argument("--humanized", type=Path, default=None,
                    help="directory with humanized versions <id>.txt (before/after)")
    ap.add_argument("--detectors", action="store_true",
                    help="enable real detectors (ollama_llm on local Ollama; "
                         "cloud ones when keys are present)")
    ap.add_argument("--perplexity", action="store_true",
                    help="add the approximate perplexity detector ollama_ppl "
                         "(expensive, sampled; needs Ollama)")
    ap.add_argument("--judge", action="store_true",
                    help="enable the LLM \"humanness\" judge (local Ollama by default; "
                         "Anthropic optional with ANTHROPIC_API_KEY)")
    ap.add_argument("--faithfulness", action="store_true",
                    help="check meaning preservation raw→humanized (cosine + meaning, "
                         "local Ollama + nomic-embed-text)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="directory for results.json (default eval/out)")
    ap.add_argument("--baseline", type=Path, default=None,
                    help="baseline for the regression gate: exit 1 on metric regressions")
    ap.add_argument("--save-baseline", action="store_true",
                    help="record the current metric snapshot as the baseline baseline.json")
    args = ap.parse_args()

    if not (args.corpus / "meta.json").exists():
        print(f"[error] not found {args.corpus / 'meta.json'}", file=sys.stderr)
        return 2

    results, env = evaluate(
        args.corpus,
        args.humanized,
        args.detectors,
        args.judge,
        use_perplexity=args.perplexity,
        use_faithfulness=args.faithfulness,
    )

    # Save results.
    args.out.mkdir(parents=True, exist_ok=True)
    results_json = {
        "env": env,
        "items": [r.as_dict() for r in results],
    }
    (args.out / "results.json").write_text(
        json.dumps(results_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # RESULTS.md — public artifact at the root of eval/.
    md = render_markdown(results, env)
    (EVAL_DIR / "RESULTS.md").write_text(md, encoding="utf-8")

    # baseline.
    baseline_path = args.out / "baseline.json"
    if args.save_baseline:
        snap = _metric_snapshot(results)
        baseline_path.write_text(
            json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[baseline] baseline written to {baseline_path}")

    print(f"[ok] results.json -> {args.out / 'results.json'}")
    print(f"[ok] RESULTS.md   -> {EVAL_DIR / 'RESULTS.md'}")
    det = env["detectors_available"]
    print(f"[info] ollama: {'up' if env.get('ollama_available') else 'no'} "
          f"({env.get('ollama_model')}); detectors: {', '.join(det) if det else 'none'}; "
          f"judge: {env.get('judge_backend') or 'none'}; "
          f"faithfulness: {'yes' if env.get('faithfulness_available') else 'no'}; "
          f"humanized: {'yes' if env['has_humanized'] else 'no'}")

    # regression gate.
    if args.baseline is not None:
        if not args.baseline.exists():
            print(f"[error] baseline {args.baseline} not found", file=sys.stderr)
            return 2
        regressions = check_regression(results, args.baseline)
        if regressions:
            print("\n[REGRESSION] metrics regressed relative to the baseline:", file=sys.stderr)
            for r in regressions:
                print(f"  ✗ {r}", file=sys.stderr)
            return 1
        print("[regression] ✓ metrics no worse than baseline")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
