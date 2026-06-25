# Security Policy

## Attack surface

humanizer-it is a local Agent Skill with no server side: a prompt (`SKILL.md`)
plus offline Python scripts (`skills/humanizer-it/scripts/`). The scripts make no
network calls, write nothing outside the paths you pass, and execute no dynamic
code. The eval harness (`eval/`) is optional and is not part of the packaged
skill.

## Supported versions

Security patches ship for the latest version on `main`. Older tags are not
supported.

## Reporting a vulnerability

Do not open a public issue for vulnerabilities. Email **ilyautov@gmail.com** or
use [GitHub private vulnerability reporting](https://github.com/ilyautov/humanizer-it/security/advisories/new).

Response within 7 days. If confirmed: a fix and a CHANGELOG mention (anonymous if
you prefer).
