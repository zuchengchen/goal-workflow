# Behavioral Eval Contract

`evals.json` is a declarative behavior contract for a future manual or agent-driven harness. Each case fixes the initial state, decisive checkpoint replies, required behaviors, forbidden actions, and observable action ordering for a high-risk workflow branch.

`checkpoint_replies` is not a complete transcript. A harness must answer routine discovery questions from the declared setup or record additional explicit fixture input, but it must never invent a design, save, overwrite, or start approval. An ordering constraint applies when both named actions occur; a terminal state may intentionally stop before the later action.

For the `verification_integrity` case, the harness must inspect the proposed verification oracle itself. It must confirm producer exit-status handling, current-run artifact provenance, pipeline and search-error semantics, and calibration against both the declared real failure and benign collision; matching a few expected words in explanatory prose is not sufficient.

The repository validator and CI currently check the JSON schema, required scenario coverage, action names, declared ordering constraints, and required verification-integrity markers. They do not run a model, inspect a live conversation trace, or claim that model behavior passed these cases. To evaluate behavior, a human reviewer or agent harness must run each prompt, capture every additional user turn plus the interaction and tool trace, and compare that evidence with the corresponding `expected` object.

## Mock Runtime Contract

`python3 tests/mock_runtime.py` exercises the bounded subagent contract without a live Codex runtime. It checks capability inspection, separate need/model/reasoning decisions, exact override propagation, post-approval dispatch, complete joins, disabled serial fallback, and failed-child handling. This is a protocol regression test, not a model-quality test.

## Manual Forward Test

Before a release that changes `skills/goal-workflow/SKILL.md`, run a real Codex Goal workflow in a disposable project and capture the tool trace. Confirm that investigating asks whether parallel subagents are useful before the coverage summary; model and reasoning are separate questions; no child is dispatched before the second approval; selected overrides reach every child; the parent joins every handle; a failed or stale child prevents completion; and `enabled: false` dispatches no child. Also run one case where dispatch or a selected override is unavailable and verify the documented stop/fallback behavior.
