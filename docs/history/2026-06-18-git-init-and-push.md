# Goal: Initialize And Push Goal Workflow Repo

> Historical design record. It describes the repository state at the time; current behavior and installation instructions live in the canonical skill and repository documentation.

## Goal Mode Objective

Follow the saved goal file at `docs/history/2026-06-18-git-init-and-push.md`; complete the task only when the verification section passes, and stop to ask if any listed stop condition occurs.

## Full Prompt

### Objective

Ensure `<repo-root>` is a valid Git repository, commit the approved `SKILL.md` change that makes goal prompts default to the current working directory, configure `origin` as `git@github.com:zuchengchen/goal-workflow.git`, and push the current local `master` branch to that remote with upstream tracking.

### Context

The repository is already initialized as a Git worktree at `<repo-root>`.

At drafting time:

- Current branch: `master`
- Existing commits:
  - `7c9b271 Simplify goal workflow invocation`
  - `f474c60 Create goal workflow skill`
- No Git remotes are configured.
- `SKILL.md` has an approved tracked change: the default goal file path is now `<YYYY-MM-DD>-<short-slug>.md` in the current working directory instead of `.codex/goals/<YYYY-MM-DD>-<short-slug>.md`.
- At the time, `2026-06-18-git-init-and-push.md` was intended to remain local workflow metadata. It is now retained under `docs/history/` as an explicit historical record.

Because `.git` already exists, do not reinitialize destructively. Reuse the existing repository state.

### Scope

Codex may:

- Inspect local Git state.
- Stage and commit only the approved `SKILL.md` path-default change.
- Configure `origin` to `git@github.com:zuchengchen/goal-workflow.git`.
- Push the current `master` branch to `origin`.
- Set upstream tracking for `master` to `origin/master`.
- Verify that the local `HEAD` commit is present on the remote branch.

### Out Of Scope

Codex must not:

- Force-push.
- Rewrite, rebase, squash, or amend existing commit history.
- Rename `master` to `main` or any other branch.
- Delete or overwrite remote branches.
- Change GitHub repository settings.
- Modify project files beyond the already-approved `SKILL.md` path-default change.
- Commit the original local goal file unless the user explicitly approves that later.

### Verification

Completion requires all applicable checks to pass:

- `git rev-parse --is-inside-work-tree` outputs `true`.
- `git branch --show-current` outputs `master`.
- `git log -1 --name-only --oneline` shows a new commit whose file list includes `SKILL.md` and does not include the original local goal file.
- `git remote get-url origin` outputs exactly `git@github.com:zuchengchen/goal-workflow.git`.
- `git push -u origin master` succeeds, or the branch is already pushed and tracking is correctly configured.
- `git rev-parse HEAD` matches the commit hash reported by `git ls-remote origin refs/heads/master`.
- `git status --short --branch` shows `master` tracking `origin/master`, with no uncommitted tracked changes. The original local goal file may remain untracked as workflow metadata.

### Stop Conditions

Stop and ask the user before proceeding if:

- SSH authentication to GitHub fails or requires credentials that are not available.
- The GitHub remote does not exist or access is denied.
- The remote `master` branch already exists with unrelated history or a non-fast-forward push would be required.
- Completing the task would require force-pushing, deleting remote state, rewriting history, or renaming the branch.
- Unexpected local tracked changes appear before pushing.
- Staging the commit would include files other than `SKILL.md`.
- Git reports an ambiguity that changes which branch, remote, or commit would be pushed.

## Notes

- Created for Codex Goal mode.
- Do not mark complete until the verification section passes or the user explicitly changes the completion standard.
