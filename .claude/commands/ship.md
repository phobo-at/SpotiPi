Commit all uncommitted changes in the SpotiPi repository and push to all configured remotes.
This is the project-specific ship command — it extends the generic workflow with version management, quality gates, CHANGELOG maintenance, and optional Pi deployment.

## Phase 1: Preflight

1. Run `git status` — verify this is a git repo. Stop if not.
2. Run `git remote` — verify at least one remote exists. Stop if none.
3. Run `git status --short` — if clean, tell the user "Nix zu shippen, Dude." and stop.
4. Run `git diff HEAD` and `git log --oneline -5` to understand the changes.
5. Classify changed files into categories:
   - **backend**: `src/`, `tests/`, `*.py`, `requirements.txt`
   - **frontend**: `frontend/src/`
   - **docs**: `CLAUDE.md`, `AGENTS.md`, `Readme.MD`, `CHANGELOG.md`, `docs/`
   - **config**: `config/`, `.env*`
   - **scripts**: `scripts/`
   - **built assets**: `static/dist/`

## Phase 2: Quality gates (run before any doc work — fail fast)

6. **If backend files changed:** run `pytest`. If it fails, stop and report errors.
7. **If frontend source changed (`frontend/src/`):**
   - Run `npm run typecheck`. Stop on failure.
   - Run `npm run build`. Stop on failure.
   - Run `npm run budget:check`. Stop on failure.
   - After build: check if `static/dist/` has unstaged changes. If yes, note they will be included in the commit.
8. **If UI behavior likely changed** (heuristic: `app.tsx`, `hooks/`, `styles.css` are in the diff):
   - Suggest: "E2E-Tests laufen lassen? (`npm run test:e2e`)" — but do NOT auto-run. Wait for user decision, then continue either way.

## Phase 3: Version management

9. Read `src/version.py` and extract the current `VERSION` value.
10. Read `Readme.MD` line 1 and `AGENTS.md` line 1 — extract their version strings.
11. **Check consistency:** do all three match?
    - If `src/version.py` was already modified in this diff: treat it as an intentional manual bump. Just ensure Readme.MD and AGENTS.md match it — fix silently if they don't.
    - If versions are inconsistent but version.py was NOT in the diff: fix Readme.MD and AGENTS.md to match version.py.
12. **Assess whether a version bump is needed** based on the diff:
    - New feature (`feat`-level change: new endpoints, new UI surface, new module) → suggest **minor** bump
    - Bug fix, hardening, small improvement → suggest **patch** bump
    - Docs-only, chore, config-only → **no bump**
    - If version.py is already in the diff (manual bump): skip this assessment
13. If a bump is suggested, show the user: "Version bump: `{current}` → `{proposed}`. Einverstanden, Dude?"
    - On yes: update `src/version.py` (`VERSION` string AND `VERSION_INFO` major/minor/patch fields), `Readme.MD` title line, `AGENTS.md` title line.
    - On no: continue without bump.

## Phase 4: Documentation sync

14. Read `CLAUDE.md`, `AGENTS.md`, `Readme.MD` and compare against the diff:
    - New environment variables → should appear in docs
    - New modules or renamed files → update AGENTS.md architecture snapshot
    - Changed CLI commands or scripts → update CLAUDE.md commands section
    - Deploy script references → must use the `.example` pattern (template is `deploy_to_pi.sh.example`, local copy is `deploy_to_pi.sh`)
15. Run `pytest --co -q 2>/dev/null | tail -1` to get the current test count. Compare with the baseline in `Readme.MD` (look for the `pytest` line under "Current baseline"). Update count and date if it changed.
16. **If version was bumped (step 13):** draft a new CHANGELOG.md entry:
    - Insert it as the first entry after the `# Changelog` header block (before the existing latest version)
    - Format: `## [x.y.z] - YYYY-MM-DD` followed by grouped changes (Features, Fixes, UI/UX, Tests, etc.)
    - Use the diff and commit messages as source material
    - Keep it concise — match the style of existing entries
    - Run `pytest -q 2>/dev/null | tail -1` to get exact pass/skip count for the Tests section

## Phase 5: Commit & Push

17. Draft a commit message following **Conventional Commits** format: `type(scope): description`
    - Common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `style`, `test`, `ci`
    - If the version was bumped, lead with the version: e.g. `feat: bump to v1.8.0 with search and queue`
    - If multiple concerns, summarize the primary change
18. Show the user:
    - All files that will be committed (staged + unstaged + auto-updated docs)
    - The proposed commit message
    - The remotes (`git remote -v`)
19. Ask: **"Alles korrekt, Dude? Soll ich committen und pushen?"** — wait for confirmation.
20. On confirmation:
    - `git add -A`
    - Commit with HEREDOC format
    - Push to every remote: `git push <remote> <branch>` for each remote from `git remote`
    - Report success or which remote failed

## Phase 6: Pi deployment

21. After successful push, automatically deploy to the Pi:
    - Check if `scripts/deploy_to_pi.sh` exists (the local, non-example copy).
    - If it doesn't exist: warn "Erstell dir erst eine lokale Kopie: `cp scripts/deploy_to_pi.sh.example scripts/deploy_to_pi.sh && chmod +x scripts/deploy_to_pi.sh`" — then skip deploy.
    - If it exists: run `./scripts/deploy_to_pi.sh` and report the deployment summary.
22. Report ship complete.

## Rules

- Never commit if working tree is clean
- Never push without explicit user confirmation
- Never skip quality gates — they run before any doc changes
- If any quality gate fails, stop and report. Do not proceed to docs or commit.
- Use the current branch name, not hardcoded "main"
- Address the user as "Dude"
- If push to any remote fails, report which one failed and why
- Keep doc updates minimal — only fix what's actually wrong or missing
- `src/version.py` is the single source of truth for version — all other files follow it
- `static/dist/` must be committed together with frontend source changes (Pi can't rebuild)
- The deploy script template is `scripts/deploy_to_pi.sh.example` — the user's local copy is `scripts/deploy_to_pi.sh` (gitignored)
