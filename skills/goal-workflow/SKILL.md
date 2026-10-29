---
name: goal-workflow
description: Turn a rough task into an executable Codex Goal mode prompt through adaptive brainstorming, optional bounded subagent planning, and a one-question-at-a-time discovery interview, with one confirmation to save and start or a save-only choice. Use when the user invokes `$goal-workflow`, asks to define or refine a durable Codex goal, or wants explicit scope, verification, risk, and subagent settings before Goal mode starts.
---

# Goal Workflow

## Purpose

Turn rough intent into a concrete Goal mode prompt, decide whether bounded parallel subagents are useful, and ask once whether to save and start it or only save it. After approval, save the exact prompt under the target project's `.codex/goals/` directory and verify it before activating or handing off the goal when launch was authorized.

Keep this workflow self-contained. Do not invoke or trigger `$define-goal`, even when that skill is installed. Apply the quality standard in this file directly.

This is a planning workflow until the goal becomes active. Do not implement the task while brainstorming, interviewing, drafting, or waiting at an approval gate unless the user explicitly leaves this workflow and asks for implementation.

## Invariants

- Use the user's language for every question, option, summary, approval request, and handoff. Do not reuse a fixed-language template.
- Ask one concise discovery question at a time. Ask two details together only when they cannot be answered independently.
- Inspect relevant local context before asking the user for facts that can be discovered safely.
- Do not write the goal file before explicit save approval tied to the complete prompt and absolute path.
- Do not activate Goal mode before explicit launch approval and successful save and exact readback. One combined save-and-start confirmation grants both permissions; do not ask for start approval again after that readback succeeds.
- A save-only choice authorizes writing the file, not launch or task execution. Never interpret silence, an unrelated confirmation, or approval of a design direction as save or launch permission.
- Do not silently expand scope or weaken verification.
- Never copy secret values, credentials, or private tokens into the draft or saved goal file; refer to their names or retrieval mechanism instead.
- Verification must not pass on absent, stale, incomplete, unreadable, or indeterminate evidence, or fail on a known benign collision in the target format.
- Do not mark a goal complete without the evidence required by its saved prompt.
- During `discovering` (the investigating phase), resolve subagent capability and policy before the coverage summary. Ask separately whether parallel subagents are needed, which currently available model to use, and which currently available reasoning depth to use when they are enabled. Do not launch a subagent before successful save, exact readback, and confirmed Goal activation.
- Never claim parallel execution unless a callable dispatch and join/status operation exists. Pass a model or reasoning override only when the user selected it and the callable operation accepts it; `inherit` means omit that override.
- Keep the parent Goal as the sole owner of shared files, shared state, Goal status, integration, and final verification. Subagents may only handle bounded work with disjoint ownership and must return a compact result or isolated artifact.

For predefined choices, use numbered options and state that the user may answer with only the number. Recommend one option when a useful default exists. For binary approvals, state the accepted affirmative and negative replies; accept `y`/`Y` and `n`/`N` as well as clear natural-language answers.

## State Machine

Track exactly one workflow state:

```text
discovering -> drafted -> draft_approved -> saved -> start_approved -> active
```

These are execution checkpoints, not separate user questions. Never skip the save or readback checkpoint.

- `discovering`: inspect context, handle existing-goal state, choose depth, brainstorm, resolve subagent policy, interview, build the coverage map, and resolve the save path.
- `drafted`: show the complete proposed prompt and absolute save path. No file has been written.
- `draft_approved`: the user has explicitly approved saving that exact prompt to that exact path. Record the choice as `execution_intent: save_and_start` or `execution_intent: save_only`. Any content or path change returns to `drafted` and invalidates both save and launch approval.
- `saved`: write succeeded and a readback exactly matched the approved content. A write attempt alone is not sufficient.
- `start_approved`: the saved file passed exact readback and launch is authorized. With `save_and_start`, enter this state automatically using the same confirmation. With `save_only`, remain `saved` until the user later explicitly requests launch of that unchanged saved goal.
- `active`: after `start_approved`, a callable goal tool confirmed activation, an existing matching goal was selected as the execution target, or the user confirmed executing the slash-command handoff.

If new information materially changes the objective, scope, verification, risks, stop conditions, or path, return to `discovering` or `drafted` as appropriate and invalidate both permissions. A save or readback failure remains `draft_approved` and forbids activation; an activation failure remains `start_approved`. Retrying the same approved content, path, and intent does not require another approval; do not treat a failed operation as success.

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

### Subagent Planning

Subagent planning is part of `discovering`/investigating and must finish before the final coverage summary and draft. It is a policy decision, not execution:

1. Inspect the current callable tool schema for subagent dispatch, join/status, cancellation, model overrides, and reasoning-depth overrides. Do not infer support from a UI label or from a model name mentioned in documentation.
2. Decide whether the goal contains at least two independent, bounded work units with disjoint ownership. Serial work, shared-file editing, or a single indivisible task does not benefit from parallel workers.
3. Ask one concise question in the user's language: whether to enable parallel subagents for this goal. Offer numbered choices, recommend enabling only when the inspection found independent work, and record an explicit `no` when the user declines.
4. If the user enables them, ask a separate question for the subagent model. Show only model identifiers accepted by the current callable schema, plus `inherit` when supported. Never invent an unavailable model or silently substitute a different one.
5. Ask a separate question for reasoning depth. Show only values accepted by the current callable schema (for example `low`, `medium`, `high`, or `xhigh` when exposed), plus `inherit` when supported. Never silently substitute a different depth.
6. If dispatch or either override is unavailable, explain the limitation and record the affected setting as `not supported`; do not promise parallel execution. If the user-selected setting cannot be passed exactly, stop and ask whether to disable subagents or revise the selection.

Record the result in the coverage map as `Answered`, `Defaulted`, `Skipped`, or `Not applicable` with the reason. The saved prompt must include `enabled`, the exact selected model or `inherit`, the exact selected reasoning value or `inherit`, the discovered dispatch/join capability, and the permitted fallback. Do not ask model or reasoning questions when the user has explicitly disabled subagents.

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
- Subagent need, runtime capability, model, reasoning depth, bounded parallelism, and fallback behavior

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

### Subagent Options

<include the investigated capability and, when applicable, `enabled: true|false`, the exact `model` or `inherit`, the exact `reasoning_effort` or `inherit`, and the allowed fallback. Do not include unsupported overrides>

## Completion Rule

Do not mark this goal complete until the objective is achieved and every required verification item passes, unless the user explicitly changes the completion standard.
```

The `Goal Mode Objective` must be concise enough to pass directly to a goal tool or `/goal`; the saved file remains the detailed source of truth.

### Approve Save And Start

Enter `drafted`, show the exact complete prompt and its absolute path, and ask one question in the user's language with these choices:

1. Save and start (recommended): save that exact content to that exact path, verify it by readback, then start Goal mode immediately.
2. Save only: save and verify the file for later use, then stop without starting Goal mode.
3. Revise or cancel: do not write or start; revise the draft or end the workflow as requested.

State that the user may reply with a number; `y`/`Y` or a clear yes to this combined question means save and start, while `n`/`N` means neither operation is approved. Explicit save-only wording always selects save only. If a reply approves saving but is unclear about launch, record `save_only` rather than inferring launch permission.

Enter `draft_approved` only after explicit approval of the displayed content and path, and retain the selected execution intent. A prior design approval, coverage approval, or overwrite approval does not satisfy this confirmation. If the user requests any content or path change, revise the draft and obtain approval for that revision; the earlier save-and-start permission no longer applies.

### Save

Only in `draft_approved`:

1. Recheck collision state immediately before writing.
2. Create the parent `.codex/goals/` directory if needed.
3. Write the exact approved content to a unique temporary file in the same directory. Refuse replacement if a collision appeared and no separate overwrite approval exists.
4. Re-read the temporary file and compare it with the approved content, then atomically rename it to the approved destination. Remove the temporary file after any failure; preserve the existing destination unless replacement was separately approved.
5. Re-read the destination from the absolute path and compare it with the approved content.
6. Enter `saved` only on an exact match; otherwise report the error and remain `draft_approved`.

Report the absolute path and a concise objective summary. For `save_and_start`, immediately enter `start_approved` and continue to Start without another approval question or ending the turn. For `save_only`, remain `saved` and provide the path for later use. Any content or path change after saving requires a new draft and renewed approval of both the content and intended action.

### Start

Recheck existing goal state after entering `start_approved`. A later explicit request to start a previously save-only goal grants launch permission for that unchanged saved goal; re-read and verify the file before entering `start_approved`, without asking the user to repeat the request.

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
- Do not silently edit the active goal file. If the goal must change materially, stop execution, obtain explicit user direction, create a versioned successor by default, and show its complete draft and path for a new combined save-and-start or save-only confirmation.
- Mark complete only when the objective is achieved and all required evidence passes. Mark blocked only when the applicable goal-tool contract permits it and the task is genuinely blocked.

At completion, report the absolute goal file path, material changes, verification results, and remaining risks.

#### Parallel Subagents

When the saved `Subagent Options` says `enabled: true`:

- Keep one parent Goal as the controller. Before each dispatch, derive a bounded batch of independent tasks with explicit inputs, outputs, ownership, and a completion signal. Do not fan out one worker per file or page without a reason, and do not dispatch when fewer than two useful independent tasks remain.
- Call only the exposed dispatch operation (for example, `spawn_agent`) and pass the saved model and reasoning values only when the operation's schema accepts them. Omit an `inherit` override so the runtime can inherit the parent capability. Use an isolated context when the runtime supports it.
- Start eligible siblings concurrently, retain every returned handle, and use the exposed join/status operation to collect every result. The parent must not proceed as if the batch finished while any handle is still pending.
- Subagents must not edit shared source, shared manifests, the active goal file, or Goal status. The parent validates returned artifacts, merges them at one integration point, runs the required verification, and decides completion.
- If dispatch, join, the selected model, or the selected reasoning value fails at runtime, record the exact failure. Continue serially only when the saved fallback explicitly permits it; otherwise stop and ask instead of silently changing the approved plan.

#### Waiting For Agents

`Waiting for agents` is a runtime wait status, not a Goal workflow state. It normally means the parent has dispatched one or more child handles and is waiting for a running or queued child result. Before waiting, inspect callable agent status and confirm the handles belong to the current Goal and batch. A long wait can also indicate a queued worker at the runtime concurrency limit, a failed child whose completion signal was not delivered, an open tool call, or stale dispatcher/UI state after a resumed Goal. Do not poll blindly, create a duplicate Goal, or claim progress without a result. If no current pending handle exists, report the runtime inconsistency and use the exposed cancellation or `/goal` lifecycle command only when the tool or command is actually supported; otherwise stop and ask the user. A Goal with `enabled: false` must not dispatch agents.

## Resume Rules

On a resumed conversation, reconstruct state and execution intent from the conversation, file readback, and observable goal state. Never infer save or launch approval from the presence of a file or an active goal alone. When a combined approval for the unchanged content and path is provable, retain it and continue from the verified checkpoint without asking again. Preserve a save-only choice until an explicit later launch request. If the approval evidence or exact approved content is missing, choose the latest provable earlier state and obtain only the missing confirmation.
