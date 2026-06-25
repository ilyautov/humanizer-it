---
description: Humanize Italian AI text (full rewrite via the humanizer-it skill)
argument-hint: <text or path to file>
---

Use the humanizer-it skill in «Full edit» mode.

Input: $ARGUMENTS

- If it's a path to a file — read the file and work with its contents.
- If it's text — work with it directly.
- If the input is empty — ask the user for text or a file path,
  and ask about the target voice (who's the author, which genre).

Run all the skill steps: voice calibration, marker removal by the catalog,
contrastive subtraction, the quad-pass audit. Remember the Fact-lock: source
facts are untouchable, inventing specifics is forbidden. Push the text toward
the native-Italian centroid (silence the anglo-calques) and bring back the
living Italian where the register allows (intercalari, ci/ne clitics,
dislocation, litote/antifrasi) — a dose, not a sprinkle.

Output: the rewritten text, then a short list (3-5 bullets) of exactly what was
fixed and why.
