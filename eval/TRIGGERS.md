# Trigger-eval — humanizer-it

Auto-generated report (`eval/run_triggers.py`). Checks NOT the quality of humanization (that's `RESULTS.md`) but the **activation boundary**: should the skill fire on a request. A light deterministic layer with no LLM — the scope-phrase guard on the description from `SKILL.md` plus the request modality (Italian / English / code). The full "by meaning" decision is made in production by the assistant from the description; here we backstop the surface boundary.

## Description guard (scope boundary)

✓ Scope phrases present (`ONLY with Italian`, `for English use the original humanizer`, `Do NOT use for: ... code`). The activation boundary in the description is intact.

## Summary

- Cases: **17** (should-trigger **9**, near-miss **8**).
- Gate accuracy: **100%** (17/17); false activations **0**, missed triggers **0**.

> A **false activation** (a near-miss taken as a trigger) is the dangerous direction for a "pushy" description: the skill would reach into code or English. That's a hard CI gate. A missed trigger is a soft warning (a failure only with `--strict`).

## Cases

| id | category | expect | modality | verdict |
|---|---|---|---|---|
| `trig_umanizza_01` | explicit_request | trigger | it | trigger ✓ |
| `trig_segni_ia_02` | explicit_request | trigger | it | trigger ✓ |
| `trig_naturale_03` | explicit_request | trigger | it | trigger ✓ |
| `trig_come_umano_04` | explicit_request | trigger | it | trigger ✓ |
| `trig_burocratese_05` | explicit_request | trigger | it | trigger ✓ |
| `trig_meno_formale_06` | explicit_request | trigger | it | trigger ✓ |
| `trig_paste_riscrivi_07` | paste_vague | trigger | it | trigger ✓ |
| `trig_paste_artificiale_08` | paste_vague | trigger | it | trigger ✓ |
| `trig_paste_migliore_09` | paste_vague | trigger | it | trigger ✓ |
| `near_code_refactor_py_01` | code | no-trigger | code | no-trigger ✓ |
| `near_code_explain_js_02` | code | no-trigger | code | no-trigger ✓ |
| `near_code_bug_py_03` | code | no-trigger | code | no-trigger ✓ |
| `near_code_sql_04` | code | no-trigger | code | no-trigger ✓ |
| `near_en_humanize_01` | english | no-trigger | en | no-trigger ✓ |
| `near_en_rewrite_02` | english | no-trigger | en | no-trigger ✓ |
| `near_en_remove_tells_03` | english | no-trigger | en | no-trigger ✓ |
| `near_en_robotic_04` | english | no-trigger | en | no-trigger ✓ |

## Near-miss by category (the skill must NOT reach in)

| category | cases | gate holds |
|---|---|---|
| code | 4 | 4/4 |
| english | 4 | 4/4 |

---

Deterministic layer: no keys, no network, no LLM — runs in CI. It checks the part of the invocation decision visible on the surface (language and modality) and that the scope boundary in the description is intact. The description is read live from `SKILL.md`.
