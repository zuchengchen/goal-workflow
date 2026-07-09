# Repository Guidelines

## Project Structure & Module Organization

The installable skill lives in `skills/goal-workflow/`. Its `SKILL.md` and `agents/openai.yaml` are the canonical release artifacts. The root-level `SKILL.md` and `agents/` directory are compatibility mirrors and must remain byte-for-byte identical to the canonical files.

Repository tooling is under `scripts/`: `validate.py` enforces structure and behavioral contracts, while the shell scripts cover validation and local install, update, and uninstall flows. Declarative scenarios live in `tests/evals.json`; `tests/README.md` explains their limits. CI is defined in `.github/workflows/validate.yml`, and historical Goal documents belong in `docs/history/`.

## Build, Test, and Development Commands

This project has no compilation or package-install step.

- `./scripts/validate.sh`: validate skill metadata, workflow invariants, mirrors, eval schema, documentation, and repository hygiene.
- `./scripts/smoke-install.sh`: exercise install, replacement, backup, dry-run, and uninstall behavior in an isolated `CODEX_HOME`.
- `python3 scripts/validate.py --skill-dir skills/goal-workflow --installed-only`: validate the canonical bundle as an installed skill.
- `git diff --check`: detect whitespace errors before committing.

When available, also run `quick_validate.py skills/goal-workflow`, matching CI behavior.

## Coding Style & Naming Conventions

Use four-space indentation and type hints in Python. Keep Bash scripts strict with `set -euo pipefail`, quote expansions, and use uppercase names for environment variables and constants. Format JSON and YAML with two-space indentation. Markdown should be concise, use descriptive headings, end with a newline, and contain no trailing whitespace.

Use lowercase kebab-case for skill names, Goal filenames, and eval case IDs, for example `verification-integrity` or `2026-07-10-api-cleanup.md`.

## Testing Guidelines

Run both validation scripts for behavior or installer changes. Add or update a focused case in `tests/evals.json` when changing workflow behavior, approval gates, or verification rules. These evals are contracts, not live model tests; material skill changes should also receive a manual or agent-driven forward test.

## Commit & Pull Request Guidelines

Recent commits use short imperative subjects such as `Expand goal workflow discovery interview` and `Add installation documentation`. Keep each commit focused.

Pull requests should explain the behavioral change, list affected skill or tooling files, report exact verification commands and results, and link relevant issues. Update `CHANGELOG.md` for user-visible changes. Screenshots are unnecessary unless a future change adds UI behavior.

## Security & Repository Hygiene

Do not commit credentials, tokens, local Goal files, caches, or generated install artifacts. `.codex/goals/` is intentionally ignored. Preserve unrelated worktree changes, and do not add extra files to the canonical skill bundle unless the validator and installation contract are updated deliberately.
