#!/usr/bin/env python3
"""Validate the goal-workflow repository or an installed skill bundle."""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path
from typing import Any


SKILL_NAME = "goal-workflow"
INSTALL_URL = (
    "https://github.com/zuchengchen/goal-workflow/"
    "tree/master/skills/goal-workflow"
)
REQUIRED_EVAL_CATEGORIES = {
    "narrow",
    "ambiguous",
    "exhaustive",
    "reject_save",
    "reject_start",
    "conflicting_goal",
    "no_goal_tool",
    "path_collision",
    "non_chinese",
    "token_budget",
    "verification_integrity",
}


class Checks:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.errors.append(f"missing file: {path}")
        except UnicodeDecodeError as exc:
            self.errors.append(f"file is not valid UTF-8: {path}: {exc}")
        except OSError as exc:
            self.errors.append(f"cannot read {path}: {exc}")
        return None


def decode_yaml_scalar(raw: str, path: Path, checks: Checks) -> str | None:
    value = raw.strip()
    if not value:
        checks.errors.append(f"empty YAML scalar in {path}")
        return None
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            checks.errors.append(f"invalid double-quoted scalar in {path}: {exc}")
            return None
        if not isinstance(parsed, str):
            checks.errors.append(f"non-string YAML scalar in {path}: {value}")
            return None
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            checks.errors.append(f"invalid single-quoted scalar in {path}: {value}")
            return None
        return value[1:-1].replace("''", "'")
    return value


def parse_frontmatter(text: str, path: Path, checks: Checks) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        checks.errors.append(f"{path} must start with a YAML frontmatter delimiter")
        return {}, text

    try:
        closing = lines.index("---", 1)
    except ValueError:
        checks.errors.append(f"{path} has no closing YAML frontmatter delimiter")
        return {}, text

    metadata: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing], start=2):
        if not line.strip():
            continue
        match = re.fullmatch(r"([a-z][a-z0-9_-]*):\s*(.+)", line)
        if not match:
            checks.errors.append(
                f"unsupported frontmatter syntax in {path}:{line_number}: {line!r}"
            )
            continue
        key, raw_value = match.groups()
        if key in metadata:
            checks.errors.append(f"duplicate frontmatter key in {path}: {key}")
            continue
        value = decode_yaml_scalar(raw_value, path, checks)
        if value is not None:
            metadata[key] = value

    body = "\n".join(lines[closing + 1 :])
    return metadata, body


def validate_frontmatter(
    skill_dir: Path, text: str, skill_path: Path, checks: Checks
) -> str:
    metadata, body = parse_frontmatter(text, skill_path, checks)
    checks.require(
        set(metadata) == {"name", "description"},
        f"{skill_path} frontmatter must contain only name and description",
    )
    checks.require(
        metadata.get("name") == SKILL_NAME,
        f"{skill_path} frontmatter name must be {SKILL_NAME!r}",
    )
    checks.require(
        skill_dir.name == metadata.get("name"),
        f"skill directory {skill_dir.name!r} must match its frontmatter name",
    )
    description = metadata.get("description", "")
    checks.require(
        1 <= len(description) <= 1024,
        f"{skill_path} description must be between 1 and 1024 characters",
    )
    checks.require(
        "$goal-workflow" in description,
        f"{skill_path} description must include the $goal-workflow trigger",
    )
    return body


def parse_openai_yaml(path: Path, text: str, checks: Checks) -> dict[str, str]:
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines or lines[0] != "interface:":
        checks.errors.append(f"{path} must contain a top-level interface mapping")
        return {}

    values: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:], start=2):
        if "\t" in line:
            checks.errors.append(f"tabs are not allowed in {path}:{line_number}")
            continue
        match = re.fullmatch(r"  ([a-z][a-z0-9_]*):\s*(.+)", line)
        if not match:
            checks.errors.append(
                f"unsupported agents metadata syntax in {path}:{line_number}: {line!r}"
            )
            continue
        key, raw_value = match.groups()
        if key in values:
            checks.errors.append(f"duplicate interface key in {path}: {key}")
            continue
        value = decode_yaml_scalar(raw_value, path, checks)
        if value is not None:
            values[key] = value
    return values


def validate_agent_metadata(skill_dir: Path, checks: Checks) -> None:
    path = skill_dir / "agents" / "openai.yaml"
    text = checks.read_text(path)
    if text is None:
        return
    values = parse_openai_yaml(path, text, checks)
    expected = {"display_name", "short_description", "default_prompt"}
    checks.require(
        set(values) == expected,
        f"{path} interface must contain exactly {sorted(expected)}",
    )

    display_name = values.get("display_name", "")
    short_description = values.get("short_description", "")
    default_prompt = values.get("default_prompt", "")
    checks.require(
        1 <= len(display_name) <= 64,
        f"{path} display_name must be between 1 and 64 characters",
    )
    checks.require(
        25 <= len(short_description) <= 64,
        f"{path} short_description must be between 25 and 64 characters",
    )
    checks.require(
        20 <= len(default_prompt) <= 1024,
        f"{path} default_prompt must be between 20 and 1024 characters",
    )
    checks.require(
        "$goal-workflow" in default_prompt,
        f"{path} default_prompt must include the literal $goal-workflow trigger",
    )


def require_pattern(
    checks: Checks, body: str, pattern: str, message: str, flags: int = re.IGNORECASE | re.DOTALL
) -> None:
    checks.require(re.search(pattern, body, flags) is not None, message)


def validate_verification_integrity(body: str, path: Path, checks: Checks) -> None:
    normalized = re.sub(r"\s+", " ", body)
    checks.require(
        "### Verification Integrity" in body,
        f"{path} must define a Verification Integrity phase",
    )
    requirements = [
        (
            r"exit status.{0,120}(?:machine-readable|structured report)",
            "prefer producer exit status or structured reports",
        ),
        (
            r"positive evidence.{0,260}zero applicable work.{0,180}discovered and executed",
            "require positive execution evidence and reject zero-work success",
        ),
        (
            r"broad prefix or keyword.{0,420}representative failure.{0,180}benign collision",
            "calibrate text matchers against failing and benign samples",
        ),
        (
            r"preserve failures.{0,120}pipelines.{0,260}`match`.{0,100}`no match`.{0,140}`search/read/parse error`",
            "preserve pipeline failures and distinguish matcher outcomes",
        ),
        (
            r"never use.{0,120}`! grep`.{0,80}`! rg`",
            "prohibit bare negated searches for absence assertions",
        ),
        (
            r"current run.{0,520}missing, stale, truncated, unreadable, unparsable",
            "reject incomplete or stale verification evidence",
        ),
        (
            r"cached evidence.{0,140}(?:key|provenance).{0,140}current inputs",
            "tie cached evidence to current inputs and target",
        ),
        (
            r"pair every negative assertion.{0,140}positive evidence",
            "pair negative assertions with positive execution evidence",
        ),
        (
            r"false positive.{0,180}verifier failure",
            "distinguish product failures from verifier false positives",
        ),
    ]
    for pattern, requirement in requirements:
        require_pattern(
            checks,
            normalized,
            pattern,
            f"{path} must {requirement}",
        )


def validate_phase_order(body: str, path: Path, checks: Checks) -> None:
    headings = [
        match.group(1).strip()
        for match in re.finditer(r"^###\s+(?:\d+\.\s*)?(.+?)\s*$", body, re.MULTILINE)
    ]
    stages = [
        ("active goal check", r"(?:existing|active).*goal|goal.*(?:existing|active)"),
        ("interview depth selection", r"^depth$|(?:interview|discovery).*(?:depth|mode)|(?:depth|mode).*(?:interview|discovery)"),
        ("brainstorming", r"brainstorm"),
        ("discovery", r"discovery"),
        ("drafting", r"draft"),
        ("save approval", r"approv.*sav|sav.*approv"),
        ("saving", r"^save$|^(?:save|write).*(?:goal|prompt).*(?:file)?$"),
        ("start approval", r"approv.*start|start.*approv"),
        ("Goal mode start or handoff", r"^start$|(?:start|handoff).*(?:goal|mode)|(?:goal|mode).*(?:start|handoff)"),
        ("execution and completion", r"execut|complet"),
    ]

    cursor = 0
    for label, pattern in stages:
        found = None
        for index in range(cursor, len(headings)):
            if re.search(pattern, headings[index], re.IGNORECASE):
                found = index
                break
        if found is None:
            checks.errors.append(
                f"{path} is missing an ordered level-3 phase heading for {label}; "
                f"headings seen: {headings}"
            )
            return
        cursor = found + 1


def validate_workflow(body: str, path: Path, checks: Checks) -> None:
    normalized = re.sub(r"\s+", " ", body)
    for mode in ("Fast", "Standard", "Exhaustive"):
        checks.require(
            re.search(rf"\b{mode}\b", body, re.IGNORECASE) is not None,
            f"{path} must define the {mode} discovery mode",
        )

    require_pattern(
        checks,
        normalized,
        r"ask (?:exactly )?one(?: [a-z-]+){0,3} question at a time",
        f"{path} must require one question at a time",
    )
    require_pattern(
        checks,
        normalized,
        r"(?:unresolved.{0,180}(?:temporary|transient)|(?:temporary|transient).{0,180}unresolved)",
        f"{path} must define Unresolved as a temporary state",
    )
    require_pattern(
        checks,
        normalized,
        r"do not\s+(?:invoke|trigger)(?:\s+or\s+(?:invoke|trigger))?\s+`?\$define-goal`?",
        f"{path} must explicitly prohibit invoking or triggering $define-goal",
    )
    for line in body.splitlines():
        lowered = line.lower()
        if re.search(r"automatically\s+(?:invoke|trigger).*\$define-goal", lowered) and "do not" not in lowered:
            checks.errors.append(
                f"{path} must not tell the agent to automatically invoke $define-goal"
            )
            break

    save_gate = (
        r"(?:do not|never)\s+(?:save|write).{0,220}(?:until.{0,120}approv|before.{0,120}approv)"
        r"|(?:save|write).{0,180}only after.{0,120}approv"
    )
    require_pattern(checks, normalized, save_gate, f"{path} must enforce approval before saving")
    require_pattern(
        checks,
        normalized,
        r"second (?:explicit )?approval|second confirmation",
        f"{path} must name the second approval before Goal mode starts",
    )
    require_pattern(
        checks,
        normalized,
        r"(?:do not|never)\s+(?:start|create|activate).{0,240}(?:until|before).{0,160}(?:second|post-save).{0,80}(?:approv|confirm)",
        f"{path} must prohibit starting Goal mode before the second approval",
    )
    checks.require("/goal pause" in body, f"{path} must document /goal pause")
    checks.require("/goal clear" in body, f"{path} must document /goal clear")
    require_pattern(
        checks,
        normalized,
        r"do not mark.{0,120}(?:goal )?complete",
        f"{path} must prohibit falsely completing an active goal",
    )
    require_pattern(
        checks,
        normalized,
        r"goal tools?.{0,80}unavailable|goal tool is not available|no (?:create )?tool is callable",
        f"{path} must define a handoff when goal tools are unavailable",
    )
    checks.require(
        "/goal <Goal Mode Objective>" in body or "/goal Follow" in body,
        f"{path} must include an exact /goal handoff form tied to the saved objective",
    )
    checks.require("collision" in body.lower(), f"{path} must define goal-file collision handling")
    checks.require("atomic" in body.lower(), f"{path} must require an atomic goal-file write")
    checks.require(
        ".codex/goals/" in body,
        f"{path} must use the repository-local .codex/goals/ location",
    )
    require_pattern(
        checks,
        normalized,
        r"user(?:'s|’s) language",
        f"{path} must keep interaction in the user's language",
    )
    checks.require("token_budget" in body, f"{path} must define token_budget handling")
    require_pattern(
        checks,
        normalized,
        r"token_budget.{0,180}(?:only|unless).{0,120}explicit|(?:only|unless).{0,120}explicit.{0,180}token_budget",
        f"{path} must set token_budget only when explicitly requested",
    )
    validate_verification_integrity(body, path, checks)
    validate_phase_order(body, path, checks)


def validate_skill_bundle(skill_dir: Path, checks: Checks, identity_only: bool = False) -> None:
    checks.require(skill_dir.name == SKILL_NAME, f"skill directory must be named {SKILL_NAME}")
    checks.require(skill_dir.is_dir(), f"skill directory does not exist: {skill_dir}")
    if not skill_dir.is_dir():
        return

    skill_path = skill_dir / "SKILL.md"
    text = checks.read_text(skill_path)
    if text is None:
        return
    body = validate_frontmatter(skill_dir, text, skill_path, checks)
    if identity_only:
        return
    validate_agent_metadata(skill_dir, checks)
    validate_workflow(body, skill_path, checks)


def require_exact_keys(
    value: dict[str, Any], expected: set[str], label: str, checks: Checks
) -> None:
    actual = set(value)
    checks.require(
        actual == expected,
        f"{label} keys must be exactly {sorted(expected)}; got {sorted(actual)}",
    )


def validate_string_list(
    value: Any, label: str, checks: Checks, *, nonempty: bool = True
) -> list[str]:
    if not isinstance(value, list):
        checks.errors.append(f"{label} must be an array")
        return []
    if nonempty and not value:
        checks.errors.append(f"{label} must not be empty")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            checks.errors.append(f"{label}[{index}] must be a non-empty string")
        else:
            result.append(item)
    checks.require(len(result) == len(set(result)), f"{label} must not contain duplicates")
    return result


def validate_eval_case(
    case: Any, index: int, actions: set[str], checks: Checks
) -> str | None:
    label = f"tests/evals.json cases[{index}]"
    if not isinstance(case, dict):
        checks.errors.append(f"{label} must be an object")
        return None
    require_exact_keys(
        case,
        {"id", "title", "category", "user_language", "prompt", "checkpoint_replies", "setup", "expected"},
        label,
        checks,
    )
    case_id = case.get("id")
    checks.require(
        isinstance(case_id, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case_id or "") is not None,
        f"{label}.id must be a lowercase kebab-case string",
    )
    for key in ("title", "user_language", "prompt"):
        checks.require(
            isinstance(case.get(key), str) and bool(case.get(key, "").strip()),
            f"{label}.{key} must be a non-empty string",
        )
    category = case.get("category")
    checks.require(category in REQUIRED_EVAL_CATEGORIES, f"{label}.category is not recognized")

    replies = case.get("checkpoint_replies")
    if not isinstance(replies, list):
        checks.errors.append(f"{label}.checkpoint_replies must be an array")
    else:
        for reply_index, reply in enumerate(replies):
            reply_label = f"{label}.checkpoint_replies[{reply_index}]"
            if not isinstance(reply, dict):
                checks.errors.append(f"{reply_label} must be an object")
                continue
            require_exact_keys(reply, {"at", "content"}, reply_label, checks)
            for key in ("at", "content"):
                checks.require(
                    isinstance(reply.get(key), str) and bool(reply.get(key, "").strip()),
                    f"{reply_label}.{key} must be a non-empty string",
                )

    setup = case.get("setup")
    setup_keys = {
        "requested_depth",
        "goal_tool",
        "active_goal",
        "goal_file",
        "explicit_token_budget",
    }
    if not isinstance(setup, dict):
        checks.errors.append(f"{label}.setup must be an object")
    else:
        require_exact_keys(setup, setup_keys, f"{label}.setup", checks)
        checks.require(
            setup.get("requested_depth") in {"auto", "fast", "standard", "exhaustive"},
            f"{label}.setup.requested_depth is invalid",
        )
        checks.require(
            setup.get("goal_tool") in {"available", "unavailable"},
            f"{label}.setup.goal_tool is invalid",
        )
        checks.require(
            setup.get("active_goal") in {"none", "matching", "conflicting"},
            f"{label}.setup.active_goal is invalid",
        )
        checks.require(
            setup.get("goal_file") in {"absent", "exists"},
            f"{label}.setup.goal_file is invalid",
        )
        budget = setup.get("explicit_token_budget")
        checks.require(
            budget is None or (isinstance(budget, int) and not isinstance(budget, bool) and budget > 0),
            f"{label}.setup.explicit_token_budget must be null or a positive integer",
        )
        if category == "token_budget":
            checks.require(isinstance(budget, int), f"{label} must provide an explicit token budget")

    expected = case.get("expected")
    expected_keys = {
        "mode",
        "required_behaviors",
        "forbidden_actions",
        "tool_order",
        "terminal_state",
    }
    if not isinstance(expected, dict):
        checks.errors.append(f"{label}.expected must be an object")
        return category if isinstance(category, str) else None
    require_exact_keys(expected, expected_keys, f"{label}.expected", checks)
    checks.require(
        expected.get("mode") in {"fast", "standard", "exhaustive"},
        f"{label}.expected.mode is invalid",
    )
    required = validate_string_list(
        expected.get("required_behaviors"), f"{label}.expected.required_behaviors", checks
    )
    forbidden = validate_string_list(
        expected.get("forbidden_actions"), f"{label}.expected.forbidden_actions", checks
    )
    for action in forbidden:
        checks.require(action in actions, f"{label} uses unknown forbidden action {action!r}")

    if category == "verification_integrity":
        raw_prompt = case.get("prompt")
        prompt = raw_prompt if isinstance(raw_prompt, str) else ""
        for marker in (
            "latexmk -xelatex",
            "stale failing",
            "!\\left",
            "! Undefined control sequence.",
        ):
            checks.require(
                marker in prompt,
                f"{label}.prompt must include verification fixture {marker!r}",
            )

        required_forbidden = {
            "accept_uncalibrated_text_matcher",
            "classify_any_bang_prefixed_line_as_tex_error",
            "ignore_producer_exit_status",
            "reuse_stale_verification_artifact",
            "treat_inconclusive_evidence_as_success",
        }
        checks.require(
            required_forbidden <= set(forbidden),
            f"{label} must forbid every verification-integrity failure mode",
        )

        behavior_text = "\n".join(required).lower()
        checks.require(
            "producer" in behavior_text and "exit status" in behavior_text,
            f"{label} must preserve the producer exit status",
        )
        checks.require(
            "same production invocation" in behavior_text,
            f"{label} must require fresh artifacts from the same invocation",
        )
        checks.require(
            "calibrat" in behavior_text
            and "!\\left" in behavior_text
            and "! undefined control sequence." in behavior_text,
            f"{label} must calibrate the declared failing and benign samples",
        )
        checks.require(
            "no match" in behavior_text
            and "search/read error" in behavior_text
            and "pipeline" in behavior_text,
            f"{label} must preserve pipeline failures and matcher error semantics",
        )
        checks.require(
            "missing" in behavior_text
            and "stale" in behavior_text
            and "inconclusive" in behavior_text,
            f"{label} must reject missing, stale, or inconclusive evidence",
        )

    tool_order = expected.get("tool_order")
    if not isinstance(tool_order, list) or not tool_order:
        checks.errors.append(f"{label}.expected.tool_order must be a non-empty array")
    else:
        for order_index, order in enumerate(tool_order):
            order_label = f"{label}.expected.tool_order[{order_index}]"
            if not isinstance(order, dict):
                checks.errors.append(f"{order_label} must be an object")
                continue
            require_exact_keys(order, {"before", "after", "reason"}, order_label, checks)
            before = order.get("before")
            after = order.get("after")
            checks.require(before in actions, f"{order_label}.before is not a known action")
            checks.require(after in actions, f"{order_label}.after is not a known action")
            checks.require(before != after, f"{order_label} must order two different actions")
            checks.require(
                isinstance(order.get("reason"), str) and bool(order.get("reason", "").strip()),
                f"{order_label}.reason must be a non-empty string",
            )

    terminal_states = {
        "awaiting_question",
        "awaiting_revision",
        "saved_not_started",
        "goal_started",
        "waiting_on_conflict",
        "path_collision_prompt",
        "slash_handoff",
    }
    checks.require(
        expected.get("terminal_state") in terminal_states,
        f"{label}.expected.terminal_state is invalid",
    )
    if category == "non_chinese":
        language = case.get("user_language", "").lower()
        checks.require(not language.startswith("zh"), f"{label} must use a non-Chinese language")
    return category if isinstance(category, str) else None


def validate_evals(path: Path, checks: Checks) -> None:
    text = checks.read_text(path)
    if text is None:
        return
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        checks.errors.append(f"invalid JSON in {path}: {exc}")
        return
    if not isinstance(document, dict):
        checks.errors.append(f"{path} must contain a JSON object")
        return
    require_exact_keys(
        document, {"schema_version", "description", "actions", "cases"}, str(path), checks
    )
    checks.require(document.get("schema_version") == 1, f"{path} schema_version must be 1")
    checks.require(
        isinstance(document.get("description"), str) and bool(document.get("description", "").strip()),
        f"{path} description must be a non-empty string",
    )
    action_list = validate_string_list(document.get("actions"), f"{path}.actions", checks)
    actions = set(action_list)
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        checks.errors.append(f"{path}.cases must be a non-empty array")
        return
    categories: list[str] = []
    ids: list[str] = []
    for index, case in enumerate(cases):
        category = validate_eval_case(case, index, actions, checks)
        if category is not None:
            categories.append(category)
        if isinstance(case, dict) and isinstance(case.get("id"), str):
            ids.append(case["id"])
    checks.require(len(ids) == len(set(ids)), f"{path} case ids must be unique")
    checks.require(
        set(categories) == REQUIRED_EVAL_CATEGORIES and len(categories) == len(REQUIRED_EVAL_CATEGORIES),
        f"{path} must contain exactly one case for each required category: "
        f"{sorted(REQUIRED_EVAL_CATEGORIES)}",
    )


def validate_mirrors(root: Path, canonical: Path, checks: Checks) -> None:
    pairs = [
        (root / "SKILL.md", canonical / "SKILL.md"),
        (root / "agents" / "openai.yaml", canonical / "agents" / "openai.yaml"),
    ]
    for legacy, source in pairs:
        try:
            checks.require(
                legacy.read_bytes() == source.read_bytes(),
                f"legacy mirror {legacy} must be byte-for-byte identical to {source}",
            )
        except FileNotFoundError as exc:
            checks.errors.append(f"missing mirror input: {exc.filename}")
        except OSError as exc:
            checks.errors.append(f"cannot compare mirror {legacy}: {exc}")


def validate_text_hygiene(root: Path, checks: Checks) -> None:
    text_suffixes = {".json", ".md", ".py", ".sh", ".yaml", ".yml"}
    text_names = {".gitignore", "LICENSE", "VERSION"}
    for path in root.rglob("*"):
        if ".git" in path.parts or not path.is_file() or path.is_symlink():
            continue
        if path.suffix not in text_suffixes and path.name not in text_names:
            continue
        text = checks.read_text(path)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            checks.require(
                not line.endswith((" ", "\t")),
                f"trailing whitespace in {path}:{line_number}",
            )
        checks.require(text.endswith("\n"), f"text file must end with a newline: {path}")


def validate_repository(root: Path, checks: Checks) -> None:
    canonical = root / "skills" / SKILL_NAME
    validate_skill_bundle(canonical, checks)
    validate_mirrors(root, canonical, checks)
    validate_text_hygiene(root, checks)

    expected_bundle_files = {"SKILL.md", "agents/openai.yaml"}
    actual_bundle_files = {
        str(path.relative_to(canonical))
        for path in canonical.rglob("*")
        if path.is_file()
    } if canonical.is_dir() else set()
    checks.require(
        actual_bundle_files == expected_bundle_files,
        "canonical skill bundle files must be exactly "
        f"{sorted(expected_bundle_files)}; got {sorted(actual_bundle_files)}",
    )

    forbidden_bundle_entries = []
    if canonical.is_dir():
        for path in canonical.rglob("*"):
            relative = path.relative_to(canonical)
            if (
                path.name in {"README.md", "INSTALL.md"}
                or "history" in relative.parts
                or re.fullmatch(r"20\d{2}-\d{2}-\d{2}-.+\.md", path.name)
            ):
                forbidden_bundle_entries.append(str(relative))
    checks.require(
        not forbidden_bundle_entries,
        "canonical skill bundle must not contain repository docs or goal history: "
        f"{sorted(forbidden_bundle_entries)}",
    )

    for doc_name in ("README.md", "INSTALL.md"):
        path = root / doc_name
        text = checks.read_text(path)
        if text is not None:
            checks.require(
                INSTALL_URL in text,
                f"{path} must include the exact canonical install URL: {INSTALL_URL}",
            )

    root_goal_files = [
        path.name
        for path in root.iterdir()
        if path.is_file() and re.fullmatch(r"20\d{2}-\d{2}-\d{2}-.+\.md", path.name)
    ]
    checks.require(
        not root_goal_files,
        f"historical goal files must not live at repository root: {sorted(root_goal_files)}",
    )
    validate_evals(root / "tests" / "evals.json", checks)
    checks.require((root / "tests" / "README.md").is_file(), "missing tests/README.md")

    version_path = root / "VERSION"
    version_text = checks.read_text(version_path)
    version = version_text.strip() if version_text is not None else ""
    semver = (
        r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
        r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    )
    checks.require(
        re.fullmatch(semver, version) is not None,
        f"{version_path} must contain exactly one semantic version",
    )
    changelog_path = root / "CHANGELOG.md"
    changelog = checks.read_text(changelog_path)
    if changelog is not None and version:
        checks.require(
            re.search(rf"(?<![0-9A-Za-z]){re.escape(version)}(?![0-9A-Za-z])", changelog)
            is not None,
            f"{changelog_path} must contain the current VERSION {version}",
        )
    license_path = root / "LICENSE"
    license_text = checks.read_text(license_path)
    if license_text is not None:
        checks.require(bool(license_text.strip()), f"{license_path} must not be empty")
    gitignore_path = root / ".gitignore"
    gitignore = checks.read_text(gitignore_path)
    if gitignore is not None:
        ignore_lines = {
            line.strip()
            for line in gitignore.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        checks.require(
            ".codex/goals/" in ignore_lines,
            f"{gitignore_path} must ignore .codex/goals/",
        )

    scripts = (
        "validate.sh",
        "install-local.sh",
        "uninstall-local.sh",
        "smoke-install.sh",
    )
    for script_name in scripts:
        path = root / "scripts" / script_name
        try:
            mode = path.stat().st_mode
        except FileNotFoundError:
            checks.errors.append(f"missing script: {path}")
            continue
        checks.require(
            bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)),
            f"script must be executable: {path}",
        )
    workflow_path = root / ".github" / "workflows" / "validate.yml"
    workflow = checks.read_text(workflow_path)
    if workflow is not None:
        for command in (
            "scripts/validate.sh",
            "scripts/smoke-install.sh",
            "quick_validate.py",
            "git diff --check",
        ):
            checks.require(
                command in workflow,
                f"{workflow_path} must run or conditionally handle {command}",
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: parent of scripts/)",
    )
    parser.add_argument("--skill-dir", type=Path, help="skill bundle to validate")
    parser.add_argument(
        "--installed-only",
        action="store_true",
        help="validate only --skill-dir as an installed bundle",
    )
    parser.add_argument(
        "--identity-only",
        action="store_true",
        help="validate only the skill directory name and SKILL.md frontmatter identity",
    )
    args = parser.parse_args()
    if args.identity_only and args.skill_dir is None:
        parser.error("--identity-only requires --skill-dir")
    if args.installed_only and args.skill_dir is None:
        parser.error("--installed-only requires --skill-dir")
    if args.identity_only and args.installed_only:
        parser.error("use only one of --identity-only and --installed-only")
    return args


def main() -> int:
    args = parse_args()
    checks = Checks()
    if args.skill_dir is not None:
        validate_skill_bundle(args.skill_dir.resolve(), checks, identity_only=args.identity_only)
        target = args.skill_dir.resolve()
    else:
        root = args.root.resolve()
        validate_repository(root, checks)
        target = root

    if checks.errors:
        for error in checks.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Validation failed with {len(checks.errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Validation passed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
