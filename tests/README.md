# Behavioral Eval Contract

`evals.json` is a declarative behavior contract for a future manual or agent-driven harness. Each case fixes the initial state, decisive checkpoint replies, required behaviors, forbidden actions, and observable action ordering for a high-risk workflow branch.

`checkpoint_replies` is not a complete transcript. A harness must answer routine discovery questions from the declared setup or record additional explicit fixture input, but it must never invent design, save, launch, or overwrite authorization. An ordering constraint applies when both named actions occur; a terminal state may intentionally stop before the later action.

At `save_start_approval`, the complete draft and absolute destination must already be visible. Option `1` or `y` grants `save_and_start` authorization for that exact content and path; option `2` or an explicit save-only reply grants only save authorization; `n` or a revision request grants neither. Record combined authorization as `approve_save_and_start` and save-only authorization as `approve_save`. `verify_saved_file` denotes a successful exact destination readback, not merely an attempted read. Combined authorization permits launch only after that action, without `ask_start_again` or a separate `approve_start` decision.

The `save-only-later-start` case sends `user_initiated_start` as an unsolicited new user turn after the save-only response has ended in `saved`. This later request is the `approve_start` action; the harness must not obtain it by accepting another assistant approval question. Revalidate the unchanged file before activation.

For `combined-save-failure`, inject a persistent write error after authorization and before the approved file is written. For `combined-readback-failure`, make the destination readback differ from the approved content after writing. In both cases, require a reported failure, no successful `verify_saved_file` event, and no Goal activation or subagent dispatch. The workflow remains `draft_approved`; the `save_failed` and `readback_failed` terminal labels describe harness outcomes rather than additional workflow states.

For `combined-content-change` and `combined-path-change`, deliver `after_save_start_approval_before_write` immediately after combined authorization and before the first filesystem mutation. The change invalidates both permissions. Stop the fixture after the revised draft is shown and a new decision is requested; do not invent renewed authorization or allow a write under the old decision.

For the `verification_integrity` case, the harness must inspect the proposed verification oracle itself. It must confirm producer exit-status handling, current-run artifact provenance, pipeline and search-error semantics, and calibration against both the declared real failure and benign collision; matching a few expected words in explanatory prose is not sufficient.

The repository validator and CI currently check the JSON schema, required scenario coverage, action names, declared ordering constraints, and required verification-integrity markers. They do not run a model, inspect a live conversation trace, or claim that model behavior passed these cases. To evaluate behavior, a human reviewer or agent harness must run each prompt, capture every additional user turn plus the interaction and tool trace, and compare that evidence with the corresponding `expected` object.

## Updater Safety Regressions

`python3 tests/updater_safety.py` checks duplicate removal and preservation, parent-directory aliases, leaf symlinks, alias changes after replacement, partial cleanup and uninstall failures, pre-commit rollback, live and crashed lock owners, initialization grace, concurrent lock reclamation, shared shell/Python transactions, and both smoke scripts' isolation. It uses temporary installations and subprocesses, with fault injection for filesystem failures. Duplicate candidates are restricted to explicit fixture paths when testing default deletion.

The smoke scripts isolate user directories and cwd before running installers and use `--keep-duplicates` for updater subprocesses: a temporary directory can still have caller-owned installations in its ancestors. The regression suite nests temporary output beneath a fixture ancestor containing a skill and verifies that caller user, project, source-checkout, and ancestor installations retain their exact contents.

CI runs the safety suite on Linux, macOS, and Windows. Process probes are tested against a real child on the current platform; Windows API results are also simulated to cover live, exited, inaccessible, and indeterminate processes. POSIX shell cases are skipped on Windows, and symlink cases are skipped if Windows denies creation. These checks do not substitute for the model forward tests below.

`python3 tests/updater_helpers.py` checks retries, compressed and expanded size budgets, archive entry limits, boundary-sized valid archives, and rejection before extraction. All downloads use local fixtures; no network request is made.

## Validation and Documented Commands

`python3 tests/validation_contract.py` checks both metadata parsers against valid strings and unsupported YAML types or syntax, verifies bundle acceptance and rejection, and confirms that private Goal files do not affect repository hygiene checks while maintained files still do.

`python3 tests/documented_commands.py` extracts the three manual uninstall snippets directly from `INSTALL.md` and runs them in temporary user and project directories. Correct identity removes only the selected directory; missing or wrong identity must preserve all files and return failure. The Bash examples are skipped on Windows.

## Mock Runtime Contract

`python3 tests/mock_runtime.py` exercises combined approval, verified saving, and bounded subagents without a live Codex runtime. It checks one-decision save/readback/activation ordering, save-only and later launch, rejection, failed writes and reads, approval invalidation, and retries with unchanged authorization. Subagent checks cover capability inspection, separate need/model/reasoning decisions, exact override propagation and inheritance, dispatch after activation, complete joins, disabled serial fallback, and failed-child handling. Empty, partial, or extra joined handle sets cannot count as completion. This is a protocol regression test, not a model-quality test.

## Manual Forward Test

Before a release that changes `skills/goal-workflow/SKILL.md`, run real Codex Goal workflows in a disposable project and capture the tool traces. Confirm that one combined decision authorizes saving and launch, exact destination readback precedes activation, and no second start question is asked. Exercise save-only, an unsolicited later start request, rejection, write and readback failures, and content or path changes that invalidate the original decision.

For parallel execution, confirm that investigating asks whether subagents are useful before the coverage summary; model and reasoning are separate questions; no child is dispatched before verified saving and Goal activation; selected overrides reach every child; the parent joins every handle; a failed or stale child prevents completion; and `enabled: false` dispatches no child. Also run one case where dispatch or a selected override is unavailable and verify the documented stop/fallback behavior.
