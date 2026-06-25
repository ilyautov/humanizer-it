# Changelog

All notable changes to humanizer-it are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/); the project
uses [semantic versioning](https://semver.org/).

## [0.1.0] — 2026-06-25

Initial release. Italian fork of [humanizer-ru](https://github.com/ilyautov/humanizer-ru) v3.11.0.

### Added
- **SKILL.md** — full Italian humanizer skill. Language-independent core ported 1:1
  from humanizer-ru (statistical-deviation principle, perplexity/burstiness,
  full-edit / audit / targeted-fix modes, contrastive subtraction, fact-lock,
  quad-pass audit, false-positive guards). UI/output language: English.
- **52-pattern catalog (A-L)** rebuilt for Italian, grounded in CORPUS-MARKERS-IT:
  burocratese / stile nominale, English calques & translationese, copula «è»
  overuse, pro-drop violations and under-used ci/ne clitics, falsi amici,
  congiuntivo (flagged as disputed — not banned), emotional sterility, persuasion
  tricks, information rhythm, and the 2025-2026 stylistic fingerprints.
- **15 hard bans** — measured Italian core (negative parallelism «non solo… ma
  anche», «gioca un ruolo cruciale», formulaic conclusions, «è importante notare
  che», em-dash, «sfruttare il potenziale», empty openings, etc.).
- **Living-Italian layer** — the differentiator vs a detector: intercalari
  (allora/insomma/magari), ci/ne clitics in idioms, left dislocation,
  litote/antifrasi irony, idioms.
- **Deterministic scanner** (`scripts/scan.py`, `humanizer_metrics/`) — rewritten
  for Italian and **dependency-free** (stdlib regex, no spaCy/pymorphy). Replaced
  the RU noun/verb ratio with Italian morphosyntax heuristics (nominalization
  density, pro-drop, ci/ne clitics) and swapped `razdel` for a stdlib segmenter.
- **Eval harness** — stratified Italian corpus (3 Italian Wikipedia human controls
  under CC BY-SA, 7 self-generated AI samples, 7 humanized rewrites); deterministic
  before/after deltas. CI is green (lint_skill, test_markers, test_score, eval).

### Notes
- All scanner thresholds are declared heuristics, to be re-calibrated on an
  Italian A/B corpus (DeSegMa → Profiling-UD).
- The candidate marker layer (empty openings, chatbot artifacts, motivational
  calques, some falsi amici) awaits native-speaker validation before any
  promotion to hard bans.
