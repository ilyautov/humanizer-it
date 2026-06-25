# humanizer-it eval harness results

Auto-generated report (`eval/run_eval.py`). Deterministic metrics are always computed; real detectors and the LLM judge are optional (see footer).

## Summary

- AI texts in the corpus: **11**, human: **24**
- Average over AI texts (raw): HARD BANS **5.0**, markers **8.5**, rhythm CV **0.346**
- No humanized versions: only the baseline (raw) is shown.

## AI texts (skill input)

| id | type | model | HARD BANS | markers | CV | nominal | dashes | verdict |
|---|---|---|---|---|---|---|---|---|
| `marketing_gpt_01` | marketing | gpt | 9 | 8 | 0.406 | 0.03 | 2 | AI |
| `marketing_gemini_02` | marketing | gemini | 7 | 14 | 0.367 | 0.033 | 0 | AI |
| `expert_claude_03` | expert | claude | 5 | 13 | 0.261 | 0.07 | 0 | AI |
| `expert_gpt_04` | expert | gpt | 5 | 13 | 0.318 | 0.066 | 0 | AI |
| `business_claude_05` | business | claude | 4 | 9 | 0.114 | 0.074 | 1 | AI |
| `business_gemini_06` | business | gemini | 5 | 13 | 0.156 | 0.033 | 0 | AI |
| `docs_gpt_07` | docs | gpt | 5 | 7 | 0.488 | 0.07 | 0 | AI |
| `social_claude_08` | social | claude | 5 | 4 | 0.588 | 0.067 | 1 | AI |
| `academic_gemini_09` | academic | gemini | 2 | 5 | 0.11 | 0.147 | 0 | AI |
| `listicle_gpt_10` | listicle | gpt | 5 | 5 | 0.544 | 0.039 | 0 | AI |
| `email_claude_11` | email | claude | 3 | 2 | 0.451 | 0.122 | 0 | AI |

## Over-correction control (human texts)

The skill should NOT want to heavily edit lively human text. Alarm if HARD BANS > 0 or markers > 5.

| id | type | HARD BANS | markers | CV | nominal | dashes | status |
|---|---|---|---|---|---|---|---|
| `wiki_garda` | reference | 0 | 0 | 0.284 | 0.021 | 0 | ✓ ok |
| `wiki_verdi` | reference | 0 | 0 | 0.314 | 0.048 | 0 | ✓ ok |
| `wiki_programmazione` | reference | 0 | 0 | 0.225 | 0.156 | 0 | ✓ ok |
| `wiki_dolomiti` | reference | 0 | 0 | 0.466 | 0.009 | 0 | ✓ ok |
| `wiki_leonardo` | reference | 0 | 1 | 0.421 | 0.056 | 0 | ✓ ok |
| `wiki_impero_romano` | reference | 0 | 0 | 0.374 | 0.017 | 0 | ✓ ok |
| `wiki_fotosintesi` | reference | 0 | 0 | 0.32 | 0.0 | 0 | ✓ ok |
| `wiki_divina_commedia` | reference | 0 | 0 | 0.193 | 0.008 | 0 | ✓ ok |
| `wiki_etna` | reference | 0 | 0 | 0.228 | 0.051 | 0 | ✓ ok |
| `wiki_rinascimento` | reference | 0 | 0 | 0.547 | 0.018 | 0 | ✓ ok |
| `wiki_galileo` | reference | 0 | 0 | 0.264 | 0.062 | 0 | ✓ ok |
| `wiki_mediterraneo` | reference | 0 | 1 | 0.644 | 0.02 | 0 | ✓ ok |
| `wiki_costituzione` | reference | 0 | 2 | 0.356 | 0.064 | 0 | ✓ ok |
| `wiki_dna` | reference | 0 | 1 | 0.254 | 0.043 | 0 | ✓ ok |
| `wiki_caravaggio` | reference | 0 | 0 | 0.658 | 0.037 | 0 | ✓ ok |
| `wiki_puccini` | reference | 0 | 2 | 0.56 | 0.036 | 0 | ✓ ok |
| `wiki_pizza` | reference | 0 | 0 | 0.294 | 0.023 | 0 | ✓ ok |
| `wiki_calcio` | reference | 0 | 0 | 0.341 | 0.013 | 0 | ✓ ok |
| `wiki_montessori` | reference | 0 | 1 | 0.089 | 0.035 | 0 | ✓ ok |
| `wiki_colosseo` | reference | 0 | 0 | 0.547 | 0.022 | 0 | ✓ ok |
| `wiki_vulcano` | reference | 0 | 0 | 0.263 | 0.011 | 0 | ✓ ok |
| `wiki_euro` | reference | 0 | 0 | 0.227 | 0.03 | 0 | ✓ ok |
| `wiki_alpi` | reference | 0 | 0 | 0.383 | 0.009 | 0 | ✓ ok |
| `wiki_caffe` | reference | 0 | 1 | 0.425 | 0.013 | 0 | ✓ ok |

Control result: **24/24** human texts passed clean.

---

### Tool availability in this run

- Local Ollama: up (chat model `gemma3:4b`, embed `nomic-embed-text`)
- Detectors requested: no; available: — (no keys/packages/Ollama)
- LLM judge requested: no; backend: — (no Ollama and no ANTHROPIC_API_KEY)
- Humanized versions: none (baseline mode)

Deterministic metrics (HARD BANS, markers, rhythm CV, nominal) are always computed and do not depend on keys, Ollama, or the network. The LLM layer (Ollama detectors, judge, faithfulness) runs on LOCAL Ollama — no Anthropic key required.
