#!/usr/bin/env python3
"""Exercise the platform-neutral updater with an isolated user environment."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update-installed-skill.py"
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

        (destination / "stale-marker").write_text("stale\n", encoding="utf-8")
        result = run_updater("--source-dir", str(ROOT), env=env)
        if result.returncode != 0:
            return result.returncode
        if (destination / "stale-marker").exists():
            raise RuntimeError("update retained a stale file")

        duplicate = home / ".agents" / "skills" / "goal-workflow"
        duplicate.parent.mkdir(parents=True)
        shutil.copytree(destination, duplicate)
        result = run_updater("--source-dir", str(ROOT), env=env)
        if result.returncode != 2:
            raise RuntimeError("updater did not refuse an unapproved duplicate")

        result = run_updater(
            "--source-dir", str(ROOT), "--prune-duplicates", env=env
        )
        if result.returncode != 0 or duplicate.exists():
            raise RuntimeError("updater did not prune the validated duplicate")

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

    print("Platform-neutral updater smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
