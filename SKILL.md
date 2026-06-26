---
name: goal-workflow
description: Interview-driven workflow for Codex Goal mode with an upfront brainstorming phase. Use when the user invokes `$goal-workflow` with a rough task such as "$goal-workflow refactor this project's auth module" or otherwise wants Codex to explore context, compare 2-3 approaches, get design-direction approval, apply define-goal-style criteria, draft a Goal mode prompt, get approval before saving it, save it to a goal file, get approval again, and then start or hand off to Goal mode execution.
---

# Goal Workflow

## Overview

Use this skill to turn a rough user intention into an approved, saved, executable Codex Goal mode prompt.

This skill coordinates five phases: brainstorm the direction, define the goal, save the goal prompt, confirm execution, and start Goal mode.

The intended simple invocation is:

```text
$goal-workflow <rough task>
```

For example:

```text
$goal-workflow 重构这个项目的认证模块
```

When invoked this way, treat the text after `$goal-workflow` as the user's rough intent. Automatically apply brainstorming behavior before `$define-goal` behavior when the request is ambiguous, design-heavy, exploratory, high-risk, or admits multiple plausible approaches. The user should not need to explicitly mention `$brainstorming` or `$define-goal`.

## Non-Negotiable Gates

- Do not save the goal file until the user approves the drafted Goal mode prompt.
- Do not start Goal mode until the user gives a second approval after the file is saved.
- Ask one concise question at a time while refining the goal, unless two details are inseparable.
- When asking a question with multiple predefined options, number the options as `1.`, `2.`, `3.`, and tell the user they may reply with only the number.
- For yes/no questions, explicitly say that `y` or `Y` means yes and `n` or `N` means no, and accept those replies.
- Prefer a reasonable default when the user is unsure, but still ask for approval before saving or starting.
- Keep the workflow in the user's language.
- Do not draft the final Goal mode prompt for ambiguous or design-heavy work until the user approves the recommended design direction.
- Do not mark a goal complete without the evidence named in the goal.

## Workflow

### 1. Start And Check Existing Goal State

Restate the user's rough intent in concrete terms.

If a goal tool is available, check the active goal state before drafting:

- If no active goal exists, continue.
- If an active goal exists and matches the user's intent, offer to refine or continue it instead of creating a duplicate.
- If an active goal exists and conflicts, ask whether the user wants to pause, clear, complete, or keep the existing goal before starting a new one. Format those choices as numbered options.

Do not block the drafting workflow if goal tools are unavailable; continue and later provide the slash command handoff.

### 2. Brainstorm Direction

Apply Claude Code / Superpowers-style `$brainstorming` behavior before defining the goal when the user's rough intent needs exploration. Do not require the user to separately invoke `$brainstorming`.

Use a full brainstorming pass when:

- the user is asking what to build, how to design it, or how to integrate a feature
- multiple implementation approaches are plausible
- the work touches user experience, architecture, public APIs, data models, migrations, security, performance, or release risk
- the verification standard depends on the chosen approach

Use a lightweight brainstorming pass for narrow or obvious tasks: briefly name the assumed approach, then continue to goal definition.

During brainstorming:

1. Inspect relevant project context before making detailed recommendations when local files, docs, issue text, or existing patterns are available.
2. Ask one concise clarifying question at a time if a missing answer changes the design direction, scope, or verification.
3. Present 2-3 viable approaches when meaningful. Number each option and state the trade-off in one sentence.
4. Recommend one approach and explain why it best fits the user's intent and the existing project.
5. Ask for approval of the design direction before drafting the final Goal mode prompt when the work is ambiguous or design-heavy. If approval is a yes/no question, include the `y`/`Y` and `n`/`N` reply hints.

Do not turn brainstorming into implementation. Its output should be a chosen direction, not code changes, unless the user explicitly switches out of this workflow.

Maintain a brainstorming draft with these fields when useful:

- Problem
- Relevant context
- Options
- Recommendation
- Open question
- Approved direction

### 3. Invoke Or Apply Define-Goal

Automatically invoke or apply `$define-goal` behavior after the user invokes `$goal-workflow`, even if the user did not mention `$define-goal`.

If the `$define-goal` skill is available, use it as the goal-definition standard. If it is unavailable, apply the quality bar below directly. Do not ask the user whether to use `$define-goal`; this skill's purpose is to do that automatically.

The target goal must answer:

- What concrete thing will be true when the task is done?
- What artifact, repo, system, environment, or user-facing behavior is involved?
- What evidence will prove completion?
- What tests, commands, metrics, examples, review criteria, or manual checks define success?
- What is in scope?
- What is out of scope?
- What should cause Codex to stop and ask instead of guessing?

Repair weak goals before proceeding. Weak goals include activity-only targets such as "make progress", "investigate", "improve things", "clean this up", or "work on X".

Use the approved brainstorming direction as input to the goal definition. If brainstorming showed that the user's request is already clear, keep the goal definition concise and do not repeat the same questions.

### 4. Interview One Detail At A Time

Maintain a working draft with these fields:

- Objective
- Context
- Scope
- Out of scope
- Verification
- Stop conditions
- Goal file path
- Brainstorming direction, when one was approved

Ask the most important missing question first. Use this priority order:

1. Desired outcome
2. Target repo, files, modules, systems, or user workflow
3. Verification command, metric, review criterion, or acceptance test
4. Scope boundaries
5. Risk constraints
6. Stop condition
7. Goal file path

When the user is unsure, offer two or three concrete choices, number them, tell the user they may reply with only the number, and recommend one. Continue until the goal quality bar is met.

### 5. Draft The Goal Mode Prompt

Create a prompt suitable for Goal mode. Keep the concise objective standalone, because it may be passed directly to `/goal` or a goal tool.

Use this structure for the full prompt:

```md
# Goal: <short title>

## Goal Mode Objective

<A concise objective that references this file if the file is the source of truth.>

## Full Prompt

### Objective

<One concrete outcome.>

### Context

<Relevant repo, files, issue, product behavior, or current state.>

### Brainstorming Direction

<Approved approach and key trade-off, or "Not needed for this narrow task.">

### Scope

<What Codex may change or inspect.>

### Out Of Scope

<What Codex should avoid.>

### Verification

<Exact commands, tests, metrics, review criteria, or manual checks required.>

### Stop Conditions

<When Codex should stop and ask instead of guessing.>

## Notes

- Created for Codex Goal mode.
- Do not mark complete until the verification section passes or the user explicitly changes the completion standard.
```

For short goals, the Goal Mode Objective may contain the full objective. For longer goals, make the saved file the source of truth and use an objective like:

```text
Follow the saved goal file at `<path>`; complete the task only when the verification section passes, and stop to ask if any listed stop condition occurs.
```

### 6. Get Approval Before Saving

Show the drafted prompt to the user before writing any file. Ask a direct approval question:

```text
这个版本可以保存为 Goal mode 提示词吗？回复 y/Y 表示可以保存，我会写入 `<path>`；回复 n/N 表示不保存，我会继续按你的修改调整。
```

If the user requests changes, revise the draft and ask again. Do not save until approved.

### 7. Save The Goal File

Default to a file in the current working directory:

```text
<YYYY-MM-DD>-<short-slug>.md
```

Use the current working directory as the base. If the user specifies a path, use that path instead.

After saving, tell the user the exact file path and summarize the objective in one or two sentences.

### 8. Get Approval Before Starting Goal Mode

After the file is saved, ask for a second confirmation:

```text
Goal 文件已经保存到 `<path>`。现在要启动 Goal mode 吗？回复 y/Y 表示启动；回复 n/N 表示暂不启动。
```

Do not start Goal mode until the user approves this second gate.

### 9. Start Goal Mode

If a goal tool is available:

1. Check the active goal state again.
2. If no active goal exists, create a goal with the saved-file objective.
3. If an active goal exists and conflicts, ask the user before replacing, clearing, or creating a new one.
4. Do not create duplicate goals.

If goal tools are not available, give the user the exact slash command:

```text
/goal Follow the saved goal file at `<path>`; complete the task only when the verification section passes, and stop to ask if any listed stop condition occurs.
```

If `/goal` is unavailable, tell the user to enable goals with:

```toml
[features]
goals = true
```

or:

```bash
codex features enable goals
```

### 10. Execute And Complete

During execution:

- Keep checking the saved goal file.
- Do not silently expand scope.
- Run the verification steps named in the file.
- If verification cannot run, explain why and ask whether the completion standard should change.
- Mark the goal complete only when the objective is achieved and no required work remains.

When finished, report:

- Goal file path
- What changed
- Verification run and results
- Any remaining risk or follow-up
