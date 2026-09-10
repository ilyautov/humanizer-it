#!/usr/bin/env python3
"""Skill self-test: tests SKILL.md against its own rules.

Catches exactly the classes of regression that otherwise only the eye catches:
  1. A missing/duplicated pattern (numbering 1..52 with no gaps).
  2. The HARD BANS count and scanner-category count diverging from markers.py.
  3. The em-dash «—» in the skill's OWN approved examples (After: / the
     "## Examples" block). The skill mandates zero em-dashes — it has no right
     to show one in its "good" output.
  4. Each approved example (After:) itself passes the scanner: zero HARD BANS.
     A skill that breaks its own bans in examples won't pass CI.
  5. No root SKILL.md mirror (it would make the CLI install the whole repo).

Run:  python scripts/lint_skill.py
Exit code 1 on any error — a gate for CI/pre-commit.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The metrics package lives INSIDE the skill (it ships with the install); the
# dev tools live in the root scripts/.
sys.path.insert(0, str(ROOT / "skills" / "humanizer-it" / "scripts"))

from humanizer_metrics.markers import HARD_BANS, SCANNER, scan_hard_bans

CANON = ROOT / "skills" / "humanizer-it" / "SKILL.md"
MIRROR = ROOT / "SKILL.md"

EXPECTED_PATTERNS = 52
EXPECTED_HARD_BANS = 15  # nucleo italiano ✅ misurato (CORPUS-MARKERS §1); lo strato
                         # candidato dei calchi sta nello scanner, non nei ban assoluti
EXPECTED_SCANNER_CATS = 20

errors: list[str] = []
notes: list[str] = []


def check_patterns(text: str) -> None:
    found = set()
    # Pattern headings: «**6.**» and ranges «**17-18.**».
    for m in re.finditer(r"^\*\*(\d{1,2})(?:-(\d{1,2}))?\.", text, re.MULTILINE):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        for n in range(start, end + 1):
            if 1 <= n <= EXPECTED_PATTERNS:
                found.add(n)
    missing = sorted(set(range(1, EXPECTED_PATTERNS + 1)) - found)
    if missing:
        errors.append(f"Missing patterns: {missing}")
    else:
        notes.append(f"✓ all {EXPECTED_PATTERNS} patterns present")


def check_counts(text: str) -> None:
    if len(HARD_BANS) != EXPECTED_HARD_BANS:
        errors.append(f"markers.HARD_BANS={len(HARD_BANS)}, expected {EXPECTED_HARD_BANS}")
    else:
        notes.append(f"✓ HARD BANS: {len(HARD_BANS)}")

    # Categories in the "## Quick scanner" section (bold labels «**...:**»).
    # markers.SCANNER is a lexical SUBSET of those categories (some scanner
    # categories are non-lexical: rhythm, structure, figurative-zero), so its
    # size need not match — it's just the engine's coverage.
    sect = re.search(r"## Quick scanner.*?(?=\n## |\Z)", text, re.DOTALL)
    scanner_cats = len(re.findall(r"^\*\*[^*\n]+:\*\*", sect.group(0), re.MULTILINE)) if sect else 0
    if scanner_cats != EXPECTED_SCANNER_CATS:
        errors.append(f"Scanner-section categories: {scanner_cats}, expected {EXPECTED_SCANNER_CATS}")
    else:
        notes.append(f"✓ scanner categories in SKILL.md: {scanner_cats}")
    notes.append(f"  (lexical engine markers.SCANNER covers {len(SCANNER)})")


def _approved_examples(text: str) -> list[tuple[int, str]]:
    """Lines of the skill's APPROVED output: 'After:' (both inline and as a
    blockquote on the next line). 'Before:' is intentionally bad — we do NOT take it.

    The label ('Before:'/'After:') often sits on a separate line from the
    blockquote itself, so we track the current label and approve a blockquote
    only if it follows After."""
    out: list[tuple[int, str]] = []
    label: str | None = None
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        m = re.match(r"^(Before|After):\s*(.*)$", s)
        if m:
            label = m.group(1)
            if m.group(2) and label == "After":
                out.append((i, m.group(2)))
            continue
        if s.startswith("> "):
            if label == "After":
                out.append((i, s[2:]))
            continue
        if s:  # any prose line resets the label
            label = None
    return out


def check_em_dash_in_examples(text: str) -> None:
    bad = [(i, ln) for i, ln in _approved_examples(text) if "—" in ln]
    if bad:
        for i, ln in bad:
            errors.append(f"Em-dash in an approved example (line {i}): {ln[:70]}")
    else:
        notes.append("✓ zero em-dashes in approved examples")


def check_examples_pass_scanner(text: str) -> None:
    failed = 0
    for i, ln in _approved_examples(text):
        hits = scan_hard_bans(ln)
        # 'Before:' intentionally contains bans; we only take After/>-good lines,
        # but just in case we filter lines that are clearly a "bad" example.
        if hits:
            failed += 1
            errors.append(f"An approved example violates a HARD BAN (line {i}): "
                          f"{', '.join(h.marker for h in hits)}")
    if not failed:
        notes.append("✓ all approved examples pass the HARD BANS scanner")


MAX_DESCRIPTION_CHARS = 1024  # Claude Code's frontmatter description limit


def check_frontmatter(text: str) -> None:
    m = re.search(r'^description:\s*"(.*)"\s*$', text, re.MULTILINE)
    if not m:
        errors.append("frontmatter: no quoted description found")
        return
    n = len(m.group(1))  # characters, not bytes
    if n > MAX_DESCRIPTION_CHARS:
        errors.append(f"frontmatter: description {n} chars > {MAX_DESCRIPTION_CHARS} "
                      "(over Claude Code's limit — auto-triggering at risk)")
    else:
        notes.append(f"✓ description: {n} chars (limit {MAX_DESCRIPTION_CHARS})")


def check_scanner_ships_with_skill() -> None:
    """The scanner must live INSIDE the skill folder (it ships with the install),
    and SKILL.md must reference it in "Audit" mode."""
    scan = CANON.parent / "scripts" / "scan.py"
    if not scan.exists():
        errors.append(f"scanner doesn't ship with the skill: missing {scan}")
        return
    if "scripts/scan.py" not in CANON.read_text(encoding="utf-8"):
        errors.append("SKILL.md doesn't reference scripts/scan.py (audit wiring lost)")
        return
    notes.append("✓ scanner is inside the skill and wired into Audit mode")


def check_sync() -> None:
    # The skill has exactly one home: skills/humanizer-it/. A root SKILL.md
    # used to mirror it so that the raw GitHub repo ZIP could be uploaded to
    # claude.ai, which wants the skill folder at the archive root. The price
    # was paid by every CLI install: with a SKILL.md at the root, the skills
    # CLI treats the WHOLE repository as the skill and copies 940K of website,
    # eval corpus and CI config into the user's agent, plus a nested second
    # copy of the skill itself. The release ZIP (scripts/build_release_zip.py,
    # 92K, skill only) serves claude.ai now, so the mirror is gone and must
    # stay gone.
    if not CANON.exists():
        errors.append(f"missing canonical file {CANON}")
        return
    if MIRROR.exists():
        errors.append(
            "root SKILL.md is back: it makes `npx skills add` copy the whole "
            "repo instead of the skill. claude.ai is served by the release ZIP"
        )
    else:
        notes.append("✓ no root SKILL.md mirror: the CLI installs the skill only")


# --- repo-wide hygiene gates (durable; lock in the IT-fork cleanup) ---------

# Detect Cyrillic via unicode escapes so THIS file holds no literal Cyrillic
# (otherwise the check would flag itself).
_CYRILLIC = re.compile("[%s-%s]" % (chr(0x400), chr(0x4FF)))

# The only files allowed to mention the parent fork (intentional cross-refs).
# The token is built by concatenation so it doesn't appear literally here.
_PARENT_REF = "humanizer-" + "ru"
_PARENT_REF_ALLOWLIST = {
    "README.md",
    "README.it.md",
    "CHANGELOG.md",
    "skills/humanizer-it/SKILL.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    "scripts/lint_skill.py",
}

# Files we scan for hygiene: text-like extensions + known extensionless names.
_TEXT_EXT = {".py", ".md", ".html", ".css", ".txt", ".json", ".yml", ".yaml",
             ".xml", ".toml", ".cfg", ".ini"}
_TEXT_NAMES = {".gitignore", ".codexignore", ".gitattributes"}
_SKIP_DIRS = {".git", "eval/out", "__pycache__", ".venv", ".pytest_cache", "assets"}


def _iter_text_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in _SKIP_DIRS):
            continue
        if path.suffix.lower() in _TEXT_EXT or path.name in _TEXT_NAMES:
            yield path, rel


def check_no_cyrillic() -> None:
    bad = []
    for path, rel in _iter_text_files():
        try:
            if _CYRILLIC.search(path.read_text(encoding="utf-8")):
                bad.append(rel)
        except (OSError, UnicodeDecodeError):
            continue
    if bad:
        errors.append("Cyrillic found in (the repo must be Cyrillic-free): "
                      + ", ".join(bad))
    else:
        notes.append("✓ repo is Cyrillic-free")


def check_parent_ref_allowlist() -> None:
    bad = []
    for path, rel in _iter_text_files():
        try:
            if _PARENT_REF in path.read_text(encoding="utf-8") and rel not in _PARENT_REF_ALLOWLIST:
                bad.append(rel)
        except (OSError, UnicodeDecodeError):
            continue
    if bad:
        errors.append(f"parent-fork ref '{_PARENT_REF}' outside the allowlist: "
                      + ", ".join(bad))
    else:
        notes.append(f"✓ '{_PARENT_REF}' only in intended cross-refs")


def check_docs_links() -> None:
    docs = ROOT / "docs"
    if not docs.is_dir():
        return
    href = re.compile(r'href="([a-z0-9][a-z0-9-]*\.html)"')
    broken = []
    for html in sorted(docs.glob("*.html")):
        for tgt in set(href.findall(html.read_text(encoding="utf-8"))):
            if not (docs / tgt).exists():
                broken.append(f"{html.name} -> {tgt}")
    if broken:
        errors.append("broken internal docs links: " + ", ".join(broken))
    else:
        notes.append("✓ docs/ internal links resolve")


def main() -> int:
    text = CANON.read_text(encoding="utf-8") if CANON.exists() else MIRROR.read_text(encoding="utf-8")
    check_patterns(text)
    check_counts(text)
    check_frontmatter(text)
    check_scanner_ships_with_skill()
    check_em_dash_in_examples(text)
    check_examples_pass_scanner(text)
    check_sync()
    check_no_cyrillic()
    check_parent_ref_allowlist()
    check_docs_links()

    print("=== lint_skill ===")
    for n in notes:
        print(" ", n)
    if errors:
        print("\nERRORS:")
        for e in errors:
            print("  ✗", e)
        return 1
    print("\nAll clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
