---
name: False positive
about: A marker or hard ban catches living human text
title: "[FP] "
labels: false-positive
---

## Which marker fired

The hard-ban / category name from the scanner report or from SKILL.md.

## Text fragment

```text
Paste the fragment it fired on (1-3 sentences is enough).
```

## Why this is human text

Genre, register, authorship. E.g. "formal legal document, the copula «è» is
normal for the genre" or "a meaningful authorial triad".

## How to reproduce

```bash
python3 skills/humanizer-it/scripts/scan.py file.txt
```
