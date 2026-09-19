#!/usr/bin/env python3
"""Regressions for updater data loss, process safety, and smoke isolation."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import ctypes
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills" / "goal-workflow"
UPDATER_PATH = ROOT / "scripts" / "update-installed-skill.py"
SPEC = importlib.util.spec_from_file_location("goal_workflow_updater", UPDATER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load updater")
UPDATER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATER)


def snapshot(path: Path) -> dict[str, bytes]:
    return {
        item.relative_to(path).as_posix(): item.read_bytes()
        for item in path.rglob("*")
        if item.is_file()
    }


class UpdaterSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="goal-workflow-safety-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.destination = self.root / "codex" / "skills" / "goal-workflow"
        shutil.copytree(CANONICAL, self.destination)

    def assert_installed(self) -> None:
        self.assertEqual(snapshot(self.destination), snapshot(CANONICAL))

    def directory_link(self, link: Path, target: Path) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            if sys.platform != "win32":
                raise
            self.skipTest(f"directory symlinks are unavailable: {exc}")

    def update(self, candidates: list[Path], *options: str) -> int:
        # Keep deletion tests entirely inside this fixture even if the caller
        # has installations in HOME, the repository, or temporary ancestors.
        output = StringIO()
        with (
            patch.object(UPDATER, "candidate_duplicate_paths", return_value=candidates),
            redirect_stdout(output),
            redirect_stderr(output),
        ):
            result = UPDATER.main(
                ["--source-dir", str(ROOT), "--dest", str(self.destination), *options]
            )
        self.assertEqual(result, 0, output.getvalue())
        return result

    def test_default_update_removes_a_distinct_duplicate(self) -> None:
        duplicate = self.root / "project" / ".agents" / "skills" / "goal-workflow"
        shutil.copytree(CANONICAL, duplicate)
        (self.destination / "stale-marker").write_text("old\n", encoding="utf-8")
        self.update([self.destination, duplicate])
        self.assertFalse(duplicate.exists())
        self.assert_installed()

    def test_keep_duplicates_preserves_the_other_installation(self) -> None:
        duplicate = self.root / "user" / ".agents" / "skills" / "goal-workflow"
        shutil.copytree(CANONICAL, duplicate)
        before = snapshot(duplicate)
        self.update([self.destination, duplicate], "--keep-duplicates")
        self.assertEqual(snapshot(duplicate), before)
        self.assert_installed()

    def test_parent_directory_alias_does_not_delete_destination(self) -> None:
        alias_parent = self.root / "user" / ".agents" / "skills"
        self.directory_link(alias_parent, self.destination.parent)
        self.update([self.destination, alias_parent / "goal-workflow"])
        self.assert_installed()

    def test_leaf_symlink_is_removed_without_deleting_destination(self) -> None:
        link = self.root / "user" / ".agents" / "skills" / "goal-workflow"
        self.directory_link(link, self.destination)
        self.update([self.destination, link])
        self.assertFalse(link.is_symlink())
        self.assert_installed()

    def test_alias_is_rechecked_after_replacement(self) -> None:
        duplicate = self.root / "project" / ".agents" / "skills" / "goal-workflow"
        shutil.copytree(CANONICAL, duplicate)
        # Check symlink support before entering the updater's exception path.
        probe = self.root / "probe"
        self.directory_link(probe, self.destination.parent)
        probe.unlink()
        install = UPDATER.install_bundle

        def replace_and_retarget(source: Path, destination: Path) -> None:
            install(source, destination)
            shutil.rmtree(duplicate.parent)
            duplicate.parent.symlink_to(destination.parent, target_is_directory=True)

        with patch.object(UPDATER, "install_bundle", side_effect=replace_and_retarget):
            self.update([self.destination, duplicate])
        self.assert_installed()

    def test_partial_old_cleanup_failure_preserves_new_installation(self) -> None:
        (self.destination / "old-only-marker").write_text("old\n", encoding="utf-8")
        remove = UPDATER.remove_path
        residues: list[Path] = []

        def partial_cleanup(path: Path) -> None:
            if path.name.startswith(".goal-workflow.replace."):
                residues.append(path)
                (path / "SKILL.md").unlink()
                raise PermissionError("simulated failure during old directory cleanup")
            remove(path)

        with patch.object(UPDATER, "remove_path", side_effect=partial_cleanup):
            with self.assertRaises(UPDATER.UpdateError) as failure:
                UPDATER.install_bundle(ROOT, self.destination)
        self.assert_installed()
        self.assertIn("new installation retained", str(failure.exception))
        self.assertEqual(len(residues), 1)
        self.assertTrue(residues[0].is_dir())
        self.assertFalse((residues[0] / "SKILL.md").exists())
        self.assertEqual(list(self.destination.parent.glob(".goal-workflow.install.*")), [])

    def test_failed_replacement_restores_the_complete_previous_installation(self) -> None:
        (self.destination / "old-only-marker").write_text("old\n", encoding="utf-8")
        before = snapshot(self.destination)
        rename = UPDATER.os.rename

        def fail_commit(source: Path, destination: Path) -> None:
            if source.parent.name.startswith(".goal-workflow.install."):
                raise PermissionError("simulated commit failure")
            rename(source, destination)

        with patch.object(UPDATER.os, "rename", side_effect=fail_commit):
            with self.assertRaisesRegex(UPDATER.UpdateError, "skill replacement failed"):
                UPDATER.install_bundle(ROOT, self.destination)
        self.assertEqual(snapshot(self.destination), before)
        self.assertEqual(list(self.destination.parent.glob(".goal-workflow.replace.*")), [])
        self.assertEqual(list(self.destination.parent.glob(".goal-workflow.install.*")), [])

    def test_staging_cleanup_failure_is_reported_without_rollback(self) -> None:
        remove = UPDATER.remove_path

        def fail_staging_cleanup(path: Path) -> None:
            if path.name.startswith(".goal-workflow.install."):
                raise PermissionError("simulated staging cleanup failure")
            remove(path)

        with patch.object(UPDATER, "remove_path", side_effect=fail_staging_cleanup):
            with self.assertRaisesRegex(UPDATER.UpdateError, "could not remove staging"):
                UPDATER.install_bundle(ROOT, self.destination)
        self.assert_installed()

    def test_native_process_probe_does_not_terminate_a_live_child(self) -> None:
        child = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.stdin.read()"],
            stdin=subprocess.PIPE,
        )
        lock = UPDATER.UpdateLock(self.destination.parent)
        try:
            self.assertTrue(lock._pid_alive(child.pid))
            self.assertIsNone(child.poll())
        finally:
            child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0)
        self.assertFalse(lock._pid_alive(child.pid))

    def test_windows_probe_only_observes_process_handles(self) -> None:
        lock = UPDATER.UpdateLock(self.destination.parent)
        cases = (
            (123, 258, 0, True),       # live process
            (123, 0, 0, False),       # exited process
            (123, 0xFFFFFFFF, 0, True),  # failed wait: do not evict
            (None, 0, 87, False),     # no such PID
            (None, 0, 5, True),       # access denied: do not evict
            (None, 0, 31, True),      # unknown error: do not evict
        )
        for handle, wait_status, error, expected in cases:
            with self.subTest(handle=handle, wait=wait_status, error=error):
                kernel = Mock()
                kernel.OpenProcess.return_value = handle
                kernel.WaitForSingleObject.return_value = wait_status
                with (
                    patch.object(UPDATER.sys, "platform", "win32"),
                    patch.object(ctypes, "WinDLL", return_value=kernel, create=True),
                    patch.object(ctypes, "get_last_error", return_value=error, create=True),
                    patch.object(UPDATER.os, "kill") as kill,
                ):
                    self.assertEqual(lock._pid_alive(123), expected)
                kill.assert_not_called()
                if handle:
                    kernel.WaitForSingleObject.assert_called_once_with(handle, 0)
                    kernel.CloseHandle.assert_called_once_with(handle)
                else:
                    kernel.CloseHandle.assert_not_called()

    def test_crashed_owner_lock_is_recovered_without_waiting(self) -> None:
        code = (
            "import importlib.util, os, sys\n"
            "from pathlib import Path\n"
            "sys.dont_write_bytecode = True\n"
            "spec = importlib.util.spec_from_file_location('updater', sys.argv[1])\n"
            "updater = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(updater)\n"
            "with updater.UpdateLock(Path(sys.argv[2])):\n"
            "    os._exit(19)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(UPDATER_PATH), str(self.destination.parent)],
            check=False,
            timeout=10,
        )
        self.assertEqual(result.returncode, 19)
        lock = UPDATER.UpdateLock(self.destination.parent)
        self.assertTrue(lock.owner_path.is_file())
        with patch.object(UPDATER.time, "sleep", side_effect=AssertionError("waited on dead owner")):
            with lock:
                owner = json.loads(lock.owner_path.read_text(encoding="utf-8"))
                self.assertEqual(owner["pid"], os.getpid())
        self.assertFalse(lock.path.exists())

    def test_old_live_owner_is_never_evicted(self) -> None:
        with UPDATER.UpdateLock(self.destination.parent) as holder:
            past = time.time() - 7200
            os.utime(holder.path, (past, past))
            contender = UPDATER.UpdateLock(self.destination.parent)
            self.assertFalse(contender._is_stale())
            with patch.object(UPDATER, "LOCK_TIMEOUT_SECONDS", 0):
                with self.assertRaisesRegex(UPDATER.UpdateError, "in progress"):
                    with contender:
                        self.fail("stole the active lock")
            self.assertTrue(holder.owner_path.is_file())

    def test_incomplete_owner_gets_only_an_initialization_grace(self) -> None:
        lock = UPDATER.UpdateLock(self.destination.parent)
        lock.path.mkdir()
        for content in (None, '{"pid":', '[]', '{"pid": 0, "token": "invalid"}'):
            with self.subTest(content=content):
                if content is not None:
                    lock.owner_path.write_text(content, encoding="utf-8")
                current = time.time()
                os.utime(lock.path, (current, current))
                self.assertFalse(lock._is_stale())
                past = current - UPDATER.LOCK_INIT_GRACE_SECONDS - 1
                os.utime(lock.path, (past, past))
                self.assertTrue(lock._is_stale())

    @unittest.skipIf(sys.platform == "win32", "POSIX installer requires Bash")
    def test_shell_cleanup_failure_preserves_new_installation(self) -> None:
        original_rm = shutil.which("rm")
        self.assertIsNotNone(original_rm)
        shim_dir = self.root / "bin"
        shim_dir.mkdir()
        shim = shim_dir / "rm"
        shim.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            'for TARGET in "$@"; do\n'
            '  case "$TARGET" in\n'
            "    */.goal-workflow.replace.*)\n"
            f'      {shlex.quote(original_rm)} -f "$TARGET/SKILL.md"\n'
            "      exit 1 ;;\n"
            "  esac\ndone\n"
            f'exec {shlex.quote(original_rm)} "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
        env = dict(os.environ, PATH=str(shim_dir) + os.pathsep + os.environ["PATH"])
        result = subprocess.run(
            ["bash", str(ROOT / "scripts" / "install-local.sh"), "--dest", str(self.destination), "--replace"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assert_installed()
        self.assertIn("new installation retained", result.stderr)

    def check_smoke_isolation(self, script: str) -> None:
        ancestor = self.root / "caller"
        checkout = ancestor / "repo"
        for directory in ("scripts", "skills"):
            shutil.copytree(ROOT / directory, checkout / directory)
        caller_user_dir = ancestor / "user"
        caller_codex_dir = ancestor / "codex"
        caller_project = ancestor / "project"
        temporary_dir = ancestor / "tmp"
        caller_project.mkdir()
        temporary_dir.mkdir()
        sentinels = [
            caller_user_dir / ".agents" / "skills" / "goal-workflow",
            caller_codex_dir / "skills" / "goal-workflow",
            checkout / ".agents" / "skills" / "goal-workflow",
            caller_project / ".agents" / "skills" / "goal-workflow",
            ancestor / ".agents" / "skills" / "goal-workflow",
        ]
        for path in sentinels:
            shutil.copytree(CANONICAL, path)
            (path / "caller-owned-marker").write_text(str(path), encoding="utf-8")
        before = [snapshot(path) for path in sentinels]
        env = dict(
            os.environ,
            HOME=str(caller_user_dir),
            USERPROFILE=str(caller_user_dir),
            CODEX_HOME=str(caller_codex_dir),
            TMPDIR=str(temporary_dir),
            TEMP=str(temporary_dir),
            TMP=str(temporary_dir),
            PYTHONDONTWRITEBYTECODE="1",
        )
        executable = "bash" if script.endswith(".sh") else sys.executable
        result = subprocess.run(
            [executable, str(checkout / "scripts" / script)],
            cwd=caller_project,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path, expected in zip(sentinels, before):
            self.assertEqual(snapshot(path), expected, f"smoke test changed {path}")

    def test_python_smoke_preserves_all_caller_installations(self) -> None:
        self.check_smoke_isolation("smoke-update.py")

    @unittest.skipIf(sys.platform == "win32", "POSIX smoke test requires Bash")
    def test_shell_smoke_preserves_all_caller_installations(self) -> None:
        self.check_smoke_isolation("smoke-install.sh")


if __name__ == "__main__":
    unittest.main(verbosity=2)
