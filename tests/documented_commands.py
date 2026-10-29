#!/usr/bin/env python3
"""Run the documented manual uninstall commands in isolated user directories."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


@unittest.skipIf(sys.platform == "win32" or BASH is None, "POSIX Bash examples only")
class DocumentedUninstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        document = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        uninstall = document.split("## 卸载\n", 1)[1].split("## 排错\n", 1)[0]
        cls.commands = [
            block
            for block in re.findall(r"```bash\n(.*?)\n```", uninstall, re.DOTALL)
            if 'rm -rf -- "$dest"' in block
        ]
        if len(cls.commands) != 3:
            raise AssertionError("expected all three documented manual uninstall commands")

    def check_commands(self, identity: str | None) -> None:
        for index, command in enumerate(self.commands):
            with self.subTest(command=index), tempfile.TemporaryDirectory(
                prefix="goal-workflow-docs-"
            ) as temporary:
                root = Path(temporary).resolve()
                user_home = root / "user home"
                codex_home = root / "codex home"
                project = root / "project"
                project.mkdir()
                destinations = [
                    codex_home / "skills" / "goal-workflow",
                    user_home / ".agents" / "skills" / "goal-workflow",
                    project / ".agents" / "skills" / "goal-workflow",
                ]
                for destination in destinations:
                    destination.mkdir(parents=True)
                    (destination / "keep.txt").write_text("preserve me\n", encoding="utf-8")
                    if identity is not None:
                        (destination / "SKILL.md").write_text(
                            f"---\nname: {identity}\n---\n", encoding="utf-8"
                        )
                before = {
                    path.relative_to(root): path.read_bytes()
                    for path in root.rglob("*")
                    if path.is_file()
                }
                environment = dict(os.environ)
                environment.update(
                    HOME=str(user_home),
                    USERPROFILE=str(user_home),
                    CODEX_HOME=str(codex_home),
                )
                # Model an ordinary shell without caller startup hooks or errexit.
                for variable in ("BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS"):
                    environment.pop(variable, None)
                result = subprocess.run(
                    [str(BASH), "--noprofile", "--norc", "-c", command],
                    cwd=project,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                expected = dict(before)
                if identity == "goal-workflow":
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse(destinations[index].exists())
                    prefix = destinations[index].relative_to(root)
                    expected = {
                        path: content
                        for path, content in before.items()
                        if prefix not in path.parents
                    }
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertTrue(destinations[index].is_dir())
                    self.assertIn("保留目录", result.stderr)
                after = {
                    path.relative_to(root): path.read_bytes()
                    for path in root.rglob("*")
                    if path.is_file()
                }
                self.assertEqual(after, expected)

    def test_wrong_identity_preserves_installations(self) -> None:
        self.check_commands("unrelated-skill")

    def test_missing_identity_preserves_installations(self) -> None:
        self.check_commands(None)

    def test_matching_identity_removes_only_the_selected_installation(self) -> None:
        self.check_commands("goal-workflow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
