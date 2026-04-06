---
name: spotipi-ship
description: Ship SpotiPi changes using the project-specific release workflow in `.claude/commands/ship.md`. Use when the user asks to ship/release/publish all pending repo changes, including quality gates, version/docs sync, commit/push, and optional Pi deployment.
---

# Spotipi Ship

Use this skill to ship repository changes in a repeatable, fail-fast flow.

## Workflow

1. Read `.claude/commands/ship.md` at runtime and treat it as the canonical project workflow.
2. Execute phases in order: Preflight, Quality gates, Version management, Documentation sync, Commit and push, Pi deployment.
3. Stop immediately on any failed quality gate. Do not continue to docs, commit, or push.
4. Keep commit/push behind explicit user confirmation.
5. Use the current branch name and push to all configured remotes; report per-remote success/failure.
6. Include `static/dist/` in the same commit when `frontend/src/` changed.
7. Treat `src/version.py` as source of truth; align `Readme.MD` and `AGENTS.md` to it.
8. Respect stricter instruction precedence: system/developer constraints first, then repository `AGENTS.md`.

## Required User Prompts

1. Ask for version bump approval when a bump is suggested and no manual bump exists.
2. Ask whether to run `npm run test:e2e` when UI behavior likely changed.
3. Before commit/push, present files, proposed conventional commit message, and remotes, then ask:
   `Alles korrekt, Dude? Soll ich committen und pushen?`

## Inputs

1. Gather preflight context from:
   - `git status`
   - `git remote`
   - `git status --short`
   - `git diff HEAD`
   - `git log --oneline -5`
2. Classify changed files by backend/frontend/docs/config/scripts/built assets as defined in the reference.
3. Read version sources:
   - `src/version.py`
   - `Readme.MD` line 1
   - `AGENTS.md` line 1

## Reference

- Canonical phase-by-phase checklist: `.claude/commands/ship.md`
