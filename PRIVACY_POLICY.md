# Privacy Policy

**humanizer-it** is a local Agent Skill: a set of instructions (`SKILL.md`) and
offline scripts (`scripts/`). The project has no server side.

## What we collect

Nothing.

- The skill sends none of your text, metadata, or telemetry anywhere.
- The deterministic scanner (`scan.py`) runs fully offline: it reads a file and
  prints a report to stdout. There are no network calls in the code.
- The eval harness (`eval/`) is optional and, by default, uses a local model via
  Ollama on your own machine. External detector adapters (GPTZero, etc.) only
  activate if you supply their API keys yourself.

## What the model sees

The skill runs inside your own AI client (Claude Code, Codex CLI, Cursor, Gemini
CLI, etc.). The text you pass for processing is handled by the model and provider
you already use, under their own policies. humanizer-it adds no new data
recipient.

## Questions

Issues: https://github.com/ilyautov/humanizer-it/issues
