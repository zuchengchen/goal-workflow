# Goal: Integrate Brainstorming Into Goal Workflow

> Historical design record. It describes an earlier implementation; current behavior and validation commands live in the canonical skill and repository documentation.

## Goal Mode Objective

Follow the saved goal file at `docs/history/2026-06-26-integrate-brainstorming.md`; complete the task only when the verification section passes, and stop to ask if any listed stop condition occurs.

## Full Prompt

### Objective

Update the current `goal-workflow` Codex skill so it includes a Claude Code / Superpowers-style brainstorming phase before goal drafting, allowing rough user requests to be explored through project-context review, one-at-a-time clarifying questions, 2-3 approach options with trade-offs, and design approval before the workflow proceeds to Goal mode prompt drafting, saving, and execution.

### Context

The target repository is `<repo-root>`.

The current skill is centered on turning a rough task into an approved, saved, executable Codex Goal mode prompt. It already applies `$define-goal` behavior, asks one concise question at a time, drafts a Goal mode prompt, requires approval before saving, and requires a second approval before starting Goal mode.

The requested change is to integrate the useful behavior of Claude Code / Superpowers `$brainstorming`, whose public workflow emphasizes exploring project context, asking clarifying questions one at a time, proposing 2-3 approaches, getting design approval before implementation, and avoiding premature coding.

### Scope

Update the current project files needed for the skill behavior and user-facing metadata, likely including:

- `SKILL.md`
- `README.md`
- `agents/openai.yaml` if the skill description or default prompt should reflect brainstorming
- `INSTALL.md` only if the integration changes installation, dependencies, or usage instructions

The integration should keep `goal-workflow` focused on Codex Goal mode. It should not become a full clone of Superpowers. It should adapt brainstorming into this repository's existing workflow by adding an early "Brainstorming Phase" before or alongside the existing define-goal phase.

The updated workflow should specify:

- when brainstorming is required
- when it can be lightweight for simple tasks
- that project context should be inspected before detailed recommendations
- that clarifying questions should be asked one at a time
- that 2-3 approaches should be presented with trade-offs and a recommendation when meaningful
- that design direction should be approved before drafting the Goal mode prompt
- that the existing two gates remain intact: approval before saving the goal file, and approval before starting Goal mode

### Out Of Scope

Do not install Claude Code, Superpowers, or a separate `$brainstorming` skill.

Do not add a visual companion, browser-based mockup server, telemetry, git-worktree flow, writing-plans flow, or forced design-doc commit workflow unless the existing `goal-workflow` project already has those patterns.

Do not introduce runtime dependencies, package managers, build systems, or scripts unless they are necessary for validation.

Do not modify unrelated untracked files such as existing generated goal files unless directly required.

Do not copy the Superpowers skill verbatim; preserve only the relevant workflow concepts in original Codex-oriented wording.

### Verification

After editing, verify all of the following:

1. `SKILL.md` still has valid YAML frontmatter with only the required `name` and `description` fields.
2. The updated skill instructions clearly describe the new brainstorming phase and where it fits relative to `$define-goal`.
3. The non-negotiable gates still require user approval before saving a goal file and a second approval before starting Goal mode.
4. The workflow still keeps the user's language and asks one concise question at a time.
5. The repository documentation reflects the new behavior where appropriate.
6. Run the skill validation script if available:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" "<repo-root>/skills/goal-workflow"
```

7. Review the final diff with:

```bash
git diff -- SKILL.md README.md INSTALL.md agents/openai.yaml
```

8. Confirm that no unrelated untracked goal files were modified.

### Stop Conditions

Stop and ask the user before proceeding if:

- the requested integration would require copying a third-party skill verbatim instead of adapting its behavior
- there is uncertainty about whether to preserve or remove an existing non-negotiable gate
- validation fails in a way that requires changing the skill format or project layout
- files outside `SKILL.md`, `README.md`, `INSTALL.md`, or `agents/openai.yaml` appear necessary to modify
- the external `$brainstorming` behavior conflicts with Codex Goal mode behavior and the conflict cannot be resolved conservatively

## Notes

- Created for Codex Goal mode.
- Do not mark complete until the verification section passes or the user explicitly changes the completion standard.
