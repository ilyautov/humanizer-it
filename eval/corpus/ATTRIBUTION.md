# Corpus attribution

## human/ — known-human control

The `wiki_*.txt` files are verbatim excerpts from the intros of Italian Wikipedia
articles. This is **known-human, contemporary, openly-licensed text** (written by
people, factual register). They serve as the "human" control for the detectors'
false-positive audit: if a detector flags them as AI, that's a false positive.

Source: it.wikipedia.org, license **CC BY-SA 4.0**. 24 article intros across
domains (geography, history, science, biography, art, music, food, sport,
economics, law), each trimmed to a comparable length, to give the false-positive
/ calibration stats a meaningful human sample. The per-article provenance URL and
license are in `meta.json` (every `type: reference` item). Examples: «Lago di
Garda», «Giuseppe Verdi», «Leonardo da Vinci», «Impero romano», «Divina
Commedia», «Galileo Galilei», «Caravaggio», «Giacomo Puccini», «Colosseo»,
«Pizza», «Euro», «Costituzione della Repubblica Italiana».

> Methodological honesty: a perfectly "pure human" contemporary corpus does not
> exist — in 2026 most text is AI-assisted. So the control is drawn from
> established encyclopedic articles, largely pre-AI editing. The register is formal
> (not colloquial), which is itself telling: detectors tend to flag formal human
> text as AI too. Note: Wikipedia uses the en-dash «–» in date ranges; that's
> normal typography of formal human text, not an AI marker (the scanner only
> counts the em-dash «—»).

## raw/ — AI texts (skill input)

Self-generated AI-style Italian text, authored to be saturated with the markers
from CORPUS-MARKERS-IT, across types (marketing, expert, business, docs) and
nominal "models". Self-generated = no copyright. They are legitimately "AI text"
as a class and demonstrate what the skill removes.

> **Legal design (see project HANDOFF):** the public eval bundles only Italian
> Wikipedia (CC BY-SA, attributed) and self-generated AI. No copyrighted news text
> (CHANGE-it / DeSegMa / Repubblica / Sole) is redistributed here — those are used
> only locally for measurement, and only derived statistics (feature vectors) leave
> that pipeline.

## humanized/ — skill output

Humanized rewrites of the matching `raw/` ids, produced by applying SKILL.md.
Used for the before/after delta in the eval harness.

## literary/ — false-positive stress case (the "Tolstoy test", Italian edition)

Canonical native-Italian literary passages that stress the scanner on legitimate
literary devices, mirroring the RU repo's `roshchin_pastiche` fixture. Three
public-domain authors, three different ways great human prose can look "machine-
like" to a surface scanner:

- `manzoni_promessi_sposi.txt` — incipit of Alessandro Manzoni, *I Promessi
  Sposi* (1840): «Quel ramo del lago di Como…». Text via Project Gutenberg eBook
  45334.
- `verga_malavoglia.txt` — incipit of Giovanni Verga, *I Malavoglia* (1881).
- `collodi_pinocchio.txt` — opening of Carlo Collodi, *Le avventure di Pinocchio*
  (1881–1883), ch. 1. The last two via the it.wikisource.org transcription.

All three works are **public domain** (authors d. 1873 / 1922 / 1890); the
Wikisource transcriptions are CC BY-SA 3.0 (per-item license in `meta.json`).

Why these (see `eval/CALIBRATION.md` for the numbers): they surface two real,
systematic false positives of the deterministic scanner.
1. **Flat rhythm.** Manzoni's and Verga's long periodic sentences score a very
   low sentence-length CV (≈0.10) — far below the "lively human ≥0.45" target —
   yet are impeccable prose. The burstiness signal must stay advisory, never a
   hard verdict.
2. **Em-dash dialogue.** Pinocchio trips the em-dash hard ban five times, because
   Italian narrative introduces speech with the *trattino di dialogo* «—». The
   em-dash ban is right for the skill's target register (AI-generated non-fiction)
   but false-positives on literary dialogue — a candidate to exempt the
   start-of-line dialogue dash, flagged for native review.
