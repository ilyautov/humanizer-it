# Contributing to humanizer-it

Thanks for wanting to help. The most valuable contributions: new confirmed
Italian AI markers (especially native-speaker validation of the candidate layer),
false positives you find, and texts for the eval corpus.

## Setup

No runtime dependencies — the scanner and tests run on a bare Python 3.11:

```bash
git clone https://github.com/ilyautov/humanizer-it.git
cd humanizer-it
python3 scripts/test_markers.py
```

## Checks before a PR

```bash
python3 scripts/test_markers.py   # metric regression tests
python3 scripts/test_score.py     # cleanliness-score regression tests
python3 scripts/lint_skill.py     # SKILL.md self-test against its own rules
```

CI runs the same on every PR.

## Project rules

- **Source of truth is `skills/humanizer-it/SKILL.md`.** The root `SKILL.md` is a
  byte-for-byte mirror: after editing, run
  `cp skills/humanizer-it/SKILL.md SKILL.md`. The lint checks the sync.
- **A marker lives in two places.** A new hard ban or scanner marker is added as a
  pair: text in `SKILL.md` + an entry in
  `skills/humanizer-it/scripts/humanizer_metrics/markers.py` + a regression test in
  `scripts/test_markers.py`. The lint cross-checks the category counts.
- **No em-dashes in approved examples.** The «—» ban is absolute; the lint catches
  violations.
- **Measured core vs candidate layer.** Hard bans are reserved for markers measured
  in Italian sources (CORPUS-MARKERS-IT §1). Plausible English calques that aren't
  yet validated by a native speaker go in the scanner, not the hard bans.
- **A new pattern needs evidence.** Show a real example where the marker appears in
  AI output and not in human text, and check for false positives (formal register,
  meaningful triads, terminological «è», etc.).

## Eval (optional)

The metrics-mode run is dependency-free:

```bash
python3 eval/run_eval.py --humanized eval/corpus/humanized
```

The full run (real detectors, LLM judge) needs the extras in
`eval/requirements-eval.txt` and a local Ollama — see that file.
