---
name: goal-workflow
description: Turn a rough task into an approved, saved, and executable Codex Goal mode prompt through adaptive brainstorming and a one-question-at-a-time discovery interview. Use when the user invokes `$goal-workflow`, asks to define or refine a durable Codex goal, or wants explicit scope, verification, risk, file-save approval, and launch approval before Goal mode starts.
---

# Goal Workflow

## Purpose

Turn rough intent into a concrete Goal mode prompt, save the approved prompt under the target project's `.codex/goals/` directory, obtain a second approval, and then activate or hand off the goal.

Keep this workflow self-contained. Do not invoke or trigger `$define-goal`, even when that skill is installed. Apply the quality standard in this file directly.

This is a planning workflow until the goal becomes active. Do not implement the task while brainstorming, interviewing, drafting, or waiting at an approval gate unless the user explicitly leaves this workflow and asks for implementation.

## Invariants

- Use the user's language for every question, option, summary, approval request, and handoff. Do not reuse a fixed-language template.
- Ask one concise discovery question at a time. Ask two details together only when they cannot be answered independently.
- Inspect relevant local context before asking the user for facts that can be discovered safely.
- Do not write the goal file before the first explicit approval.
- Do not activate Goal mode before the second explicit approval, given only after a successful save and readback.
- Never interpret silence, an unrelated confirmation, or approval of a design direction as either approval gate.
- Do not silently expand scope or weaken verification.
- Never copy secret values, credentials, or private tokens into the draft or saved goal file; refer to their names or retrieval mechanism instead.
- Verification must not pass on absent, stale, incomplete, unreadable, or indeterminate evidence, or fail on a known benign collision in the target format.
- Do not mark a goal complete without the evidence required by its saved prompt.

For predefined choices, use numbered options and state that the user may answer with only the number. Recommend one option when a useful default exists. For binary approvals, state the accepted affirmative and negative replies; accept `y`/`Y` and `n`/`N` as well as clear natural-language answers.

## State Machine

Track exactly one workflow state:

```text
discovering -> drafted -> draft_approved -> saved -> start_approved -> active
```

Never skip or merge states.

- `discovering`: inspect context, handle existing-goal state, choose depth, brainstorm, interview, build the coverage map, and resolve the save path.
- `drafted`: show the complete proposed prompt and absolute save path. No file has been written.
- `draft_approved`: the user has explicitly approved saving that exact prompt to that exact path. Any content or path change returns to `drafted` and invalidates the approval.
- `saved`: write succeeded and a readback exactly matched the approved content. A write attempt alone is not sufficient.
- `start_approved`: after the save, the user explicitly approved starting Goal mode. Declining leaves the workflow in `saved`.
- `active`: after `start_approved`, a callable goal tool confirmed activation, an existing matching goal was selected as the execution target, or the user confirmed executing the slash-command handoff.

If new information materially changes the objective, scope, verification, risks, stop conditions, or path, return to `discovering` or `drafted` as appropriate. A save failure remains `draft_approved`; an activation failure remains `start_approved`.

## Workflow

### Existing Goal

At the beginning and again immediately before activation, inspect current goal state with a callable read tool when one is available.

- If no goal is active, continue.
- If a matching goal is active, ask whether to continue it, prepare a revised successor, or cancel this workflow. Continuing the existing goal exits this new-goal workflow without pretending that its states were traversed. Do not create a duplicate.
- If a conflicting goal is active, identify the conflict and allow drafting for later only if the user wants that. Do not activate the new goal until the conflict is resolved.

Distinguish callable tools from slash commands:

- Call only operations actually exposed by the current tool schema. Use `get_goal` for inspection, `create_goal` for activation, and `update_goal` for status changes only when those tools are actually callable and their schemas permit the intended action. A tool set may allow reading or creating a goal while not allowing pause, clear, resume, or objective replacement.
- Use completion or blocked status only when their semantic conditions are genuinely met. Never mark an unfinished goal complete or blocked merely to free the active-goal slot.
- When the required lifecycle action is not callable, tell the user to perform the supported slash-command fallback, such as `/goal pause` or `/goal clear`. If command support is uncertain, direct the user to `/goal` help rather than inventing a tool capability.
- After a slash command, re-read goal state when possible or ask the user to confirm the result. Do not claim the state changed merely because the command was shown.

### Depth

Select an interview depth from explicit user preference first, then task risk and ambiguity:

- `fast`: use for narrow, reversible, low-risk work with an obvious target and verification path. Ask only questions whose answers can materially change the goal; infer low-risk facts from inspected context and expose those in the coverage summary.
- `standard`: use by default. Cover every discovery area, but ask only about gaps that cannot be resolved confidently from the request and project context.
- `exhaustive`: use when the user requests detailed or comprehensive planning, or when the task involves security, privacy, destructive migration, public contracts, multiple systems, major architecture, costly rollout, or unclear acceptance criteria. Explore alternatives, failure modes, rollout, and rollback explicitly.

Tell the user which depth was selected and why. The user may change it at any time. Depth changes interview length, not the state machine, approval gates, coverage map, or goal quality standard.

### Brainstorm

Inspect relevant files, documentation, history, and local conventions before recommending a direction.

For ambiguous or design-heavy work:

1. State the problem and relevant constraints.
2. Present two or three viable approaches with one-sentence tradeoffs.
3. Recommend one approach and explain why it fits the context.
4. Ask for explicit approval of the direction before moving to the final discovery summary.

For narrow work, record the assumed direction and why a comparison is unnecessary. Brainstorming chooses a direction; it does not produce implementation changes. Approval of a direction is not approval to save or start.

### Discovery

Maintain a coverage map containing every area below:

- Outcome and measurable definition of done
- Current problem, target project, affected components, current behavior, and desired behavior
- Users, stakeholders, and externally visible behavior
- In-scope work and out-of-scope boundaries
- Existing conventions, constraints, dependencies, and relevant history
- Approved approach, alternatives, and tradeoffs
- Interfaces, APIs, CLI, UI, configuration, data, persistence, and migrations
- Security, privacy, permissions, secrets, and compliance
- Errors, observability, operations, performance, reliability, scalability, and concurrency
- Compatibility, rollout, rollback, documentation, and release communication
- Automated verification commands, oracle semantics, evidence freshness, calibration samples, expected work discovery, and manual acceptance criteria
- Risks, assumptions, external dependencies, and stop conditions
- Goal file location and safe filename
- Explicitly requested goal-tool options, including a token budget when present

Assign each area one status:

- `Answered`: established by the user or reliable inspected evidence.
- `Defaulted`: a proposed default that the user explicitly accepted.
- `Skipped`: the user explicitly chose not to resolve it.
- `Not applicable`: evidence shows it does not apply; include a short reason.
- `Unresolved`: it still lacks a reliable answer. This is a valid temporary status.

Do not label an uncertain area `Not applicable`. At the selected depth, repeatedly choose the highest-impact `Unresolved` area, ask one question, record the answer, and update newly revealed risks.

Before drafting, show a concise coverage summary grouped by status. Map every remaining `Unresolved` item to exactly one treatment:

- an explicit assumption in the prompt;
- an out-of-scope boundary; or
- a stop condition that forbids guessing during execution.

Keep its history visible as `Unresolved -> <treatment>`; do not relabel it as answered. Ask whether the user wants to investigate further or draft with those mappings. Do not draft until the user accepts the mapping. If an unresolved item would make execution unsafe or impossible, keep interviewing instead of converting it into an assumption.

### Verification Integrity

Treat each automated verification item as an oracle that must distinguish success, product failure, and verifier or infrastructure failure.

- Prefer the producing tool's documented exit status and machine-readable or structured report. Require positive evidence that the intended work ran against the intended target and produced the expected result; absence of a known error string alone is not sufficient. When a runner can succeed with zero applicable work, assert that the expected tests or items were discovered and executed.
- If text matching is unavoidable, match the diagnostic record's severity, origin, delimiters, and required multiline context, not a broad prefix or keyword. Distinguish real failures from echoed input, source or code excerpts, wrapped continuation lines, summaries such as `0 errors`, allowed warnings, and other benign collisions. Calibrate every nontrivial custom matcher or parser against at least one representative failure and one benign collision, including multiline, wrapped, escaped, or continuation forms when the format permits them.
- Make setup, the producer, and every assertion contribute to the final exit status. Preserve failures through pipelines and wrappers; avoid early-terminating live search pipelines that can change an upstream status; and distinguish `match`, `no match`, and `search/read/parse error`. Never use a bare negated search such as `! grep` or `! rg` for an absence assertion, or `|| true` when it can convert an operational failure into success.
- Verify only complete evidence from the current run. Use a clean or unique output location or remove prior outputs first; capture every relevant stream in stable noninteractive form; then require expected reports, logs, and artifacts to exist, be readable, be nonempty when applicable, and belong to the current target and run. Accept cached evidence only when its key or provenance is demonstrably tied to the current inputs and target. Treat missing, stale, truncated, unreadable, unparsable, or otherwise indeterminate evidence as inconclusive, never as success.
- Pair every negative assertion with positive evidence that the intended build, test, scanner, or code path actually ran. If a sound automated oracle cannot be defined, use an explicit manual acceptance criterion or a stop condition instead of an uncalibrated heuristic.

For example, `rg '^!' build.log` is not by itself a sound TeX-error oracle: diagnostic, source, or verbatim continuation text may also begin with `!`. Prefer the compiler's status or structured report, or use a format-aware parser calibrated with both a real error record and a benign `!\left...` continuation.

### Draft

Apply this built-in quality standard:

- State one concrete outcome, not an activity such as "investigate", "make progress", "improve things", or "clean this up".
- Identify the project, artifact, system, environment, or user-visible behavior involved.
- Define evidence of completion through exact commands, tests, metrics, examples, review criteria, or manual checks that satisfy Verification Integrity.
- Make scope and out-of-scope boundaries explicit.
- Preserve approved constraints, decisions, assumptions, unresolved mappings, risks, and external dependencies.
- State when execution must stop and ask rather than guess.
- Make completion impossible to claim before required verification passes, unless the user explicitly changes that standard.

Resolve the save path before asking for save approval:

1. Determine the target project root from reliable workspace or repository evidence. Use `<project-root>/.codex/goals/` when the root is known; otherwise use `<cwd>/.codex/goals/`.
2. Build `<YYYY-MM-DD>-<slug>.md`. Use a lowercase ASCII slug matching `[a-z0-9]+(?:-[a-z0-9]+)*`; transliterate or summarize non-ASCII titles, limit it to 60 characters, and use a deterministic generic slug if needed.
3. Resolve and display an absolute normalized path. Never present `~`, a relative path, or a path whose base is ambiguous.
4. Check whether the path already exists before approval. For a collision, recommend a new collision-free name. Overwriting requires a separate, explicit approval tied to the exact absolute path; do not bundle overwrite consent with prompt approval and never overwrite silently.

Draft the complete file in this form:

```md
# Goal: <short title>

## Goal Mode Objective

Follow the saved goal file at `<absolute-path>`; complete the task only when all required verification passes, and stop to ask if any listed stop condition occurs.

## Full Prompt

### Objective

<one concrete outcome>

### Context

<target, current state, relevant evidence, and constraints>

### Approved Direction

<chosen approach and key tradeoff, or why comparison was unnecessary>

### Discovery Decisions

<answers, accepted defaults, skipped areas, not-applicable reasons, assumptions, and unresolved mappings>

### Scope

<allowed changes and inspections>

### Out Of Scope

<excluded work>

### Verification

<exact automated commands with explicit success semantics, freshness and calibration safeguards, plus manual acceptance criteria>

### Risks And Rollout

<risks, dependencies, compatibility, rollout, and rollback>

### Stop Conditions

<conditions that require asking instead of guessing>

### Goal Tool Options

<include only explicitly requested options, such as `token_budget: <positive-integer>`; omit this section when none were requested>

## Completion Rule

Do not mark this goal complete until the objective is achieved and every required verification item passes, unless the user explicitly changes the completion standard.
```

The `Goal Mode Objective` must be concise enough to pass directly to a goal tool or `/goal`; the saved file remains the detailed source of truth.

### Approve Save

Enter `drafted`, show the exact complete prompt and its absolute path, and ask in the user's language whether to save that exact content to that exact path. Clearly identify this as the first approval gate.

If the user requests any change, revise the draft and ask again. Enter `draft_approved` only after an unambiguous affirmative answer. A prior design approval, coverage approval, or overwrite approval does not satisfy this gate.

### Save

Only in `draft_approved`:

1. Recheck collision state immediately before writing.
2. Create the parent `.codex/goals/` directory if needed.
3. Write the exact approved content to a unique temporary file in the same directory. Refuse replacement if a collision appeared and no separate overwrite approval exists.
4. Re-read the temporary file and compare it with the approved content, then atomically rename it to the approved destination. Remove the temporary file after any failure; preserve the existing destination unless replacement was separately approved.
5. Re-read the destination from the absolute path and compare it with the approved content.
6. Enter `saved` only on an exact match; otherwise report the error and remain `draft_approved`.

Report the absolute path and a concise objective summary. Any content or path change after saving requires a new draft and a new save approval.

### Approve Start

Only after successful readback, ask in the user's language whether to start Goal mode from the saved file. Clearly identify this as the second approval gate and name the accepted affirmative and negative replies.

Enter `start_approved` only after an unambiguous affirmative answer. If the user declines, remain `saved` and provide the absolute file path for later use.

### Start

Recheck existing goal state after entering `start_approved`.

- If `create_goal` or an equivalent compatible tool is callable and no conflicting goal is active, create the goal with the concise `Goal Mode Objective`.
- Pass `token_budget` only when the user explicitly requested a token budget or supplied its numeric value, and preserve that value in the saved `Goal Tool Options` section so resumed execution can recover it. Never infer it from interview depth, task size, or available context.
- If a matching goal is already active, do not create a duplicate; confirm that it is the execution target.
- If a conflict remains, use the Existing Goal rules and remain `start_approved` until resolved.
- If no create tool is callable, provide the exact localized handoff command: `/goal <Goal Mode Objective>`. Do not claim activation until the user confirms running it or observable goal state confirms it.
- If Goal mode itself is unavailable, explain how to enable the host's goals feature, but do not claim the workflow is `active`.

Enter `active` only after activation is confirmed.

### Execute

Once active, treat the saved goal file as read-only and as the source of truth:

- Work only within its scope and approved direction.
- Stop on its stop conditions instead of guessing.
- Run every required verification item and report actual results.
- Treat skipped, zero-work, missing, stale, unreadable, truncated, or otherwise indeterminate evidence as failed verification unless the saved prompt explicitly defines it as acceptable.
- When a check fails, distinguish product failure from verifier or environment failure. Do not change product behavior merely to appease a false positive or treat a verifier failure as success. Repair a project-owned verifier only when scope permits and the acceptance criterion remains unchanged; otherwise follow the material goal-revision rules.
- Do not silently edit the active goal file. If the goal must change materially, stop execution, obtain explicit user direction, create a versioned successor by default, and repeat the draft, save, and start approvals as applicable.
- Mark complete only when the objective is achieved and all required evidence passes. Mark blocked only when the applicable goal-tool contract permits it and the task is genuinely blocked.

At completion, report the absolute goal file path, material changes, verification results, and remaining risks.

## Resume Rules

On a resumed conversation, reconstruct state from the conversation, file readback, and observable goal state. Never infer either approval from the presence of a file or an active goal alone. If evidence is incomplete, choose the latest provable earlier state and repeat the necessary gate.
