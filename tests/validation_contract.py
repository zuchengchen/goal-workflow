#!/usr/bin/env python3
"""Regressions for metadata string parsing and repository hygiene scope."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from types import ModuleType
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills" / "goal-workflow"


def load_module(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module("goal_workflow_validator", "validate.py")
UPDATER = load_module("goal_workflow_updater", "update-installed-skill.py")


class MetadataStringTests(unittest.TestCase):
    def test_supported_strings_have_identical_values_in_both_parsers(self) -> None:
        cases = (
            ("goal-workflow", "goal-workflow"),
            ("Use `$goal-workflow` to plan a task.", "Use `$goal-workflow` to plan a task."),
            ("https://example.test/#plan", "https://example.test/#plan"),
            ('"true"', "true"),
            ('"123"', "123"),
            ('"[$goal-workflow]"', "[$goal-workflow]"),
            ('"中文 goal"', "中文 goal"),
            (r'"quoted \"word\""', 'quoted "word"'),
            ("'Don''t skip approval'", "Don't skip approval"),
            ("'key: value # literal text'", "key: value # literal text"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                checks = VALIDATOR.Checks()
                self.assertEqual(
                    VALIDATOR.decode_yaml_scalar(raw, Path("metadata.yaml"), checks),
                    expected,
                )
                self.assertEqual(checks.errors, [])
                self.assertEqual(UPDATER._decode_scalar(raw), expected)

    def test_implicit_types_and_unsupported_syntax_are_rejected_by_both_parsers(self) -> None:
        cases = (
            "", "[$goal-workflow]", "{name: goal-workflow}",
            "true", "FALSE", "Yes", "no", "ON", "off", "null", "NULL", "~",
            "0", "-42", "+42", "0xFF", "0o77", "0123", "1_000", "1:23",
            "3.14", "-.5", ".inf", "+.Inf", ".NaN", "2026-10-29",
            "!tag value", "!!str value", "&anchor value", "*alias",
            "|", ">", "# comment", "value # comment", "key: value",
            "- item", "? item", ": item", "%YAML", "@directive", "`code`", "<<", "=",
            "'unclosed", "'unescaped ' quote'", "'first' 'second'",
            '"unclosed', r'"invalid \q escape"',
        )
        for raw in cases:
            with self.subTest(raw=raw):
                checks = VALIDATOR.Checks()
                self.assertIsNone(
                    VALIDATOR.decode_yaml_scalar(raw, Path("metadata.yaml"), checks)
                )
                self.assertTrue(checks.errors)
                with self.assertRaises(UPDATER.UpdateError):
                    UPDATER._decode_scalar(raw)

    def test_canonical_bundle_passes_both_validators(self) -> None:
        checks = VALIDATOR.Checks()
        VALIDATOR.validate_skill_bundle(CANONICAL, checks)
        self.assertEqual(checks.errors, [])
        UPDATER.validate_bundle(CANONICAL)

    def test_non_string_fields_fail_full_bundle_validation(self) -> None:
        cases = (
            ("SKILL.md", "description", "[$goal-workflow]"),
            ("SKILL.md", "description", "{$goal-workflow: plan}"),
            ("agents/openai.yaml", "display_name", "true"),
            ("agents/openai.yaml", "short_description", "12345678901234567890123456789"),
            ("agents/openai.yaml", "default_prompt", '["Use $goal-workflow to plan a task."]'),
        )
        for filename, field, raw in cases:
            with self.subTest(field=field, raw=raw), tempfile.TemporaryDirectory() as temporary:
                skill = Path(temporary) / "goal-workflow"
                shutil.copytree(CANONICAL, skill)
                path = skill / filename
                text, count = re.subn(
                    rf"^(\s*{field}:).*?$",
                    lambda match: f"{match.group(1)} {raw}",
                    path.read_text(encoding="utf-8"),
                    flags=re.MULTILINE,
                )
                self.assertEqual(count, 1)
                path.write_text(text, encoding="utf-8")
                checks = VALIDATOR.Checks()
                VALIDATOR.validate_skill_bundle(skill, checks)
                self.assertTrue(checks.errors)
                with self.assertRaises(UPDATER.UpdateError):
                    UPDATER.validate_bundle(skill)


class CombinedApprovalTests(unittest.TestCase):
    def test_missing_safety_requirements_fail_workflow_validation(self) -> None:
        body = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
        changes = (
            (
                "explicit launch approval and successful save and exact readback",
                "the presence of a saved file",
                "explicit launch approval, successful save, and exact readback",
            ),
            (
                "do not ask for start approval again after that readback succeeds",
                "ask for start approval again after that readback succeeds",
                "forbid asking for start approval again",
            ),
            (
                "A save-only choice authorizes writing the file, not launch or task execution",
                "A save-only choice authorizes writing the file and launch",
                "keep save-only approval separate",
            ),
            (
                "invalidates both save and launch approval",
                "retains save and launch approval",
                "invalidate both permissions",
            ),
            (
                "A save or readback failure remains `draft_approved` and forbids activation",
                "A save or readback failure permits activation",
                "forbid activation when saving or exact readback fails",
            ),
            (
                "Retrying the same approved content, path, and intent does not require another approval",
                "Retrying the same approved content, path, and intent requires another approval",
                "preserve authorization when retrying",
            ),
        )
        for original, replacement, error in changes:
            with self.subTest(error=error):
                self.assertIn(original, body)
                checks = VALIDATOR.Checks()
                VALIDATOR.validate_workflow(body.replace(original, replacement), Path("SKILL.md"), checks)
                self.assertTrue(any(error in message for message in checks.errors), checks.errors)

    def test_old_two_question_phase_layout_is_rejected(self) -> None:
        body = (CANONICAL / "SKILL.md").read_text(encoding="utf-8")
        for changed, error in (
            (body.replace("### Approve Save And Start", "### Approve Save"), "combined save and start approval"),
            (body.replace("### Start\n", "### Approve Start\n\n### Start\n"), "separate Approve Start phase"),
        ):
            with self.subTest(error=error):
                self.assertNotEqual(changed, body)
                checks = VALIDATOR.Checks()
                VALIDATOR.validate_workflow(changed, Path("SKILL.md"), checks)
                self.assertTrue(any(error in message for message in checks.errors), checks.errors)

    def test_evals_require_verified_save_contract_and_reject_second_approval_action(self) -> None:
        for mode in ("missing_action", "obsolete_action", "missing_forbidden"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                document = json.loads((ROOT / "tests" / "evals.json").read_text(encoding="utf-8"))
                if mode == "missing_action":
                    document["actions"].remove("verify_saved_file")
                    error = "must define combined approval and verified-save actions"
                elif mode == "obsolete_action":
                    document["actions"].append("start_before_second_approval")
                    error = "must not retain the obsolete second-approval action"
                else:
                    document["cases"][0]["expected"]["forbidden_actions"].remove("start_before_verified_save")
                    error = "must forbid launching without authorization or verified save"
                path = Path(temporary) / "evals.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                checks = VALIDATOR.Checks()
                VALIDATOR.validate_evals(path, checks)
                self.assertTrue(any(error in message for message in checks.errors), checks.errors)


class RepositoryHygieneTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="goal-workflow-validation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repository"
        self.root.mkdir()
        for name in (
            ".gitignore", "AGENTS.md", "CHANGELOG.md", "INSTALL.md", "LICENSE",
            "README.md", "SKILL.md", "VERSION",
        ):
            shutil.copy2(ROOT / name, self.root / name)
        for name in (".github", "agents", "docs", "scripts", "skills", "tests"):
            shutil.copytree(ROOT / name, self.root / name)

    def test_private_goals_and_dependencies_do_not_change_repository_validation(self) -> None:
        checks = VALIDATOR.Checks()
        VALIDATOR.validate_text_hygiene(self.root, checks)
        self.assertEqual(checks.errors, [])
        for relative in (
            ".codex/goals/private-goal.md", "node_modules/package/README.md",
            ".venv/library.py", "local-notes.md",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"private content  \nno final newline")
        checks = VALIDATOR.Checks()
        VALIDATOR.validate_text_hygiene(self.root, checks)
        self.assertEqual(checks.errors, [])
        self.assertFalse((self.root / ".git").exists())

    def test_repository_owned_files_still_report_whitespace_errors(self) -> None:
        for relative in ("README.md", "scripts/example.py", "docs/example.md", ".github/example.yml"):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_bytes() if path.exists() else None
                path.write_bytes(b"tracked content  \nno final newline")
                checks = VALIDATOR.Checks()
                VALIDATOR.validate_text_hygiene(self.root, checks)
                self.assertTrue(any(f"trailing whitespace in {path}:1" in error for error in checks.errors))
                self.assertTrue(any(f"end with a newline: {path}" in error for error in checks.errors))
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
