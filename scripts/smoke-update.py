#!/usr/bin/env python3
"""Exercise the platform-neutral updater with an isolated user environment."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update-installed-skill.py"
UNINSTALLER = ROOT / "scripts" / "uninstall-installed-skill.py"
VALIDATOR = ROOT / "scripts" / "validate.py"


def run_updater(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(UPDATER), *args],
        cwd=ROOT,
        env=env,
        text=True,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-workflow-smoke-") as temp_dir:
        temp = Path(temp_dir)
        home = temp / "home"
        codex_home = temp / "codex-home"
        env = os.environ.copy()
        env.update(
            {
                "CODEX_HOME": str(codex_home),
                "HOME": str(home),
                "USERPROFILE": str(home),
            }
        )
        destination = codex_home / "skills" / "goal-workflow"

        result = run_updater("--source-dir", str(ROOT), env=env)
        if result.returncode != 0:
            return result.returncode
        if not (destination / "SKILL.md").is_file():
            raise RuntimeError("updater did not create the isolated destination")

        holder_code = (
            "import importlib.util\n"
            "from pathlib import Path\n"
            "import sys\n"
            "import time\n"
            "sys.dont_write_bytecode = True\n"
            "root = Path(sys.argv[1])\n"
            "spec = importlib.util.spec_from_file_location('updater', root / "
            "'scripts' / 'update-installed-skill.py')\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "with module.UpdateLock(Path(sys.argv[2])):\n"
            "    time.sleep(0.6)\n"
        )
        holder = subprocess.Popen(
            [sys.executable, "-c", holder_code, str(ROOT), str(destination.parent)],
            cwd=ROOT,
            env=env,
        )
        time.sleep(0.1)
        result = run_updater("--source-dir", str(ROOT), env=env)
        holder.wait(timeout=10)
        if result.returncode != 0:
            raise RuntimeError("updater failed while waiting for the update lock")

        (destination / "stale-marker").write_text("stale\n", encoding="utf-8")
        result = run_updater("--source-dir", str(ROOT), env=env)
        if result.returncode != 0:
            return result.returncode
        if (destination / "stale-marker").exists():
            raise RuntimeError("update retained a stale file")

        malicious_source = temp / "malicious-source"
        shutil.copytree(ROOT / "skills", malicious_source / "skills")
        (malicious_source / "scripts").mkdir()
        marker = malicious_source / "validator-executed.marker"
        (malicious_source / "scripts" / "validate.py").write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n",
            encoding="utf-8",
        )
        result = run_updater("--source-dir", str(malicious_source), env=env)
        if result.returncode != 0 or marker.exists():
            raise RuntimeError("updater executed a source checkout validator")

        parent = destination.parent
        replacement = parent / ".goal-workflow.replace.smoke"
        staging = parent / ".goal-workflow.install.smoke" / "goal-workflow"
        destination.rename(replacement)
        staging.mkdir(parents=True)
        (staging / "stale-marker").write_text("stale\n", encoding="utf-8")
        result = run_updater("--source-dir", str(ROOT), env=env)
        if result.returncode != 0 or not (destination / "SKILL.md").is_file():
            raise RuntimeError("updater did not recover an interrupted replacement")
        if replacement.exists() or staging.parent.exists():
            raise RuntimeError("updater left interrupted replacement residue")

        duplicate = home / ".agents" / "skills" / "goal-workflow"
        duplicate.parent.mkdir(parents=True)
        shutil.copytree(destination, duplicate)
        result = run_updater("--source-dir", str(ROOT), "--keep-duplicates", env=env)
        if result.returncode != 0 or not duplicate.exists():
            raise RuntimeError("updater did not honor --keep-duplicates")

        result = run_updater("--source-dir", str(ROOT), env=env)
        if result.returncode != 0 or duplicate.exists():
            raise RuntimeError("updater did not prune the validated duplicate by default")

        validation = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--skill-dir",
                str(destination),
                "--installed-only",
            ],
            cwd=ROOT,
            env=env,
            check=False,
        )
        if validation.returncode != 0:
            return validation.returncode

        uninstall = subprocess.run(
            [sys.executable, str(UNINSTALLER)],
            cwd=ROOT,
            env=env,
            check=False,
        )
        if uninstall.returncode != 0 or destination.exists():
            raise RuntimeError("cross-platform uninstaller did not remove the destination")

    print("Platform-neutral updater smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
