---
description: Audit text for AI signs without editing (scanner + skill breakdown)
argument-hint: <text or path to file>
---

Use the humanizer-it skill in «Audit» mode: show the markers, rewrite nothing.

Input: $ARGUMENTS

- If it's a path to a file — work with the file; if it's text — save it to a
  temporary file for the scanner.
- If the input is empty — ask for text or a path.

Order per the skill: first the machine half — run the deterministic scanner.
It is dependency-free (plain Python stdlib), so it runs anywhere python3 is
available:

```
python3 <skill folder>/scripts/scan.py <file>
```

If for any reason the scanner can't run, conduct the audit by hand from the
marker catalog. The audit must happen no matter what.

On top of the scanner report add judgment: flag false positives (genre, formal
register, meaningful triads, a single authorial em-dash), and prioritize fixes
from the most damning to the cosmetic. At the end give a verdict on the
scanner's cleanliness scale and 3-5 key recommendations.
