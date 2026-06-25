#!/usr/bin/env python3
"""Packaging smoke-test: proves what actually ships in the skill works.

The installed unit is `skills/humanizer-it/` (SKILL.md + scripts/). This test
checks, from OUTSIDE the repo tree, that:
  1. SKILL.md frontmatter is valid (name, description within the Claude Code
     limit, MIT license).
  2. The metrics package imports standalone from the skill's own scripts dir
     (no dependency on the repo root or any third-party package).
  3. scan.py runs as a subprocess from a clean working directory and returns
     valid English-UI output + JSON: hard bans on saturated AI text, zero on
     living Italian. Exit code is 1 when hard bans are found, 0 when clean.
  4. The shipped scanner pulls in no razdel/pymorphy/spaCy (dependency-free).

Run:  python scripts/test_package.py
Exit code 1 on any failure — a gate for CI/pre-commit.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "humanizer-it"
SKILL_MD = SKILL_DIR / "SKILL.md"
SCAN = SKILL_DIR / "scripts" / "scan.py"
METRICS = SKILL_DIR / "scripts" / "humanizer_metrics"
MAX_DESCRIPTION_CHARS = 1024

AI_TEXT = ("Nel mondo di oggi l'IA gioca un ruolo cruciale. È importante notare "
           "che non solo ottimizza, ma anche trasforma.")
HUMAN_TEXT = ("Allora, l'anno scorso ho messo l'IA in tre progetti. Due sono "
              "volati. Il terzo? Saltato: il team aveva smesso di controllare "
              "quello che usciva. Mica colpa del modello, eh.")

failures: list[str] = []
notes: list[str] = []


def check(cond: bool, ok: str, bad: str) -> None:
    (notes if cond else failures).append(ok if cond else bad)


def check_frontmatter() -> None:
    text = SKILL_MD.read_text(encoding="utf-8")
    if not text.startswith("---"):
        failures.append("SKILL.md: no YAML frontmatter")
        return
    front = text[3:text.find("\n---", 3)]
    name = re.search(r'^name:\s*(.+?)\s*$', front, re.MULTILINE)
    desc = re.search(r'^description:\s*"(.*)"\s*$', front, re.MULTILINE)
    lic = re.search(r'^license:\s*(.+?)\s*$', front, re.MULTILINE)
    check(bool(name) and name.group(1) == "humanizer-it",
          "✓ frontmatter name=humanizer-it",
          f"frontmatter name wrong: {name.group(1) if name else None}")
    check(bool(desc) and 0 < len(desc.group(1)) <= MAX_DESCRIPTION_CHARS,
          f"✓ description {len(desc.group(1)) if desc else 0} chars (≤{MAX_DESCRIPTION_CHARS})",
          "frontmatter description missing or over the limit")
    check(bool(lic) and lic.group(1).upper() == "MIT",
          "✓ license MIT", "frontmatter license is not MIT")


def check_standalone_import() -> None:
    """Import the metrics package using ONLY the skill's scripts dir on path."""
    code = (
        "import sys; sys.path.insert(0, r'%s'); "
        "from humanizer_metrics import analyze; "
        "r = analyze('Allora, non ci penso. Magari domani.'); "
        "print(r.as_dict()['hard_ban_count'])"
    ) % (SKILL_DIR / "scripts")
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, cwd=tempfile.gettempdir())
    check(proc.returncode == 0 and proc.stdout.strip().isdigit(),
          "✓ humanizer_metrics imports standalone from the skill dir",
          f"standalone import failed: {proc.stderr.strip()[:200]}")


def _run_scan(text: str) -> tuple[int, dict | None, str]:
    """Run scan.py from a clean temp cwd, feeding text on stdin. Returns
    (exit_code, parsed_json_or_None, plain_stdout)."""
    tmp = tempfile.gettempdir()
    j = subprocess.run([sys.executable, str(SCAN), "-", "--json"],
                       input=text, capture_output=True, text=True, cwd=tmp)
    p = subprocess.run([sys.executable, str(SCAN), "-"],
                       input=text, capture_output=True, text=True, cwd=tmp)
    parsed = None
    try:
        parsed = json.loads(j.stdout)
    except json.JSONDecodeError:
        pass
    return p.returncode, parsed, p.stdout


def check_scan_ai() -> None:
    rc, parsed, out = _run_scan(AI_TEXT)
    check(parsed is not None and parsed.get("hard_ban_count", 0) > 0,
          f"✓ scan.py flags AI text (hard bans: {parsed.get('hard_ban_count') if parsed else '?'})",
          "scan.py did not flag saturated AI text")
    check(rc == 1, "✓ scan.py exits 1 when hard bans found",
          f"scan.py exit code on AI text was {rc}, expected 1")
    check("CLEANLINESS" in out and "Morphosyntax" in out,
          "✓ scan.py prints English-UI report",
          "scan.py output is missing the English-UI labels")


def check_scan_human() -> None:
    rc, parsed, _ = _run_scan(HUMAN_TEXT)
    check(parsed is not None and parsed.get("hard_ban_count", 1) == 0,
          "✓ scan.py: zero hard bans on living Italian",
          f"scan.py found hard bans on clean text: {parsed.get('hard_ban_count') if parsed else '?'}")
    check(rc == 0, "✓ scan.py exits 0 on clean text",
          f"scan.py exit code on clean text was {rc}, expected 0")


def check_dependency_free() -> None:
    # Match real import statements, not mentions in comments (the code says
    # "no pymorphy" etc. on purpose).
    imp = re.compile(r"^\s*(?:import|from)\s+(razdel|pymorphy3?|spacy|stanza)\b",
                     re.MULTILINE)
    banned = set()
    for p in list(METRICS.glob("*.py")) + [SCAN]:
        banned.update(imp.findall(p.read_text(encoding="utf-8")))
    check(not banned,
          "✓ shipped scanner is dependency-free (no razdel/pymorphy/spaCy)",
          f"shipped scanner imports a heavy dep: {sorted(banned)}")


def main() -> int:
    for fn in (check_frontmatter, check_standalone_import, check_scan_ai,
               check_scan_human, check_dependency_free):
        fn()
    print("=== test_package ===")
    for n in notes:
        print(" ", n)
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  ✗", f)
        return 1
    print("\nAll clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
