#!/usr/bin/env python3
"""Remove a validated goal-workflow installation on any supported OS."""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True


def load_updater():
    path = Path(__file__).with_name("update-installed-skill.py")
    spec = importlib.util.spec_from_file_location("goal_workflow_updater", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load updater helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove a validated goal-workflow installation."
    )
    parser.add_argument("--dest", help="skill destination")
    parser.add_argument("--dry-run", action="store_true", help="validate without removing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        updater = load_updater()
    except (OSError, RuntimeError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    try:
        destination = updater.resolve_destination(args.dest)
        with updater.UpdateLock(destination.parent):
            recovery_messages: list[str] = []
            if not args.dry_run:
                recovery_messages = updater.recover_interrupted_update(destination)
            if not updater.path_exists(destination) or not destination.is_dir():
                raise updater.UpdateError(
                    f"uninstall target is not an existing directory: {destination}"
                )
            updater.validate_bundle(destination, identity_only=True)
            if args.dry_run:
                for message in recovery_messages:
                    print(message)
                print(f"Would uninstall validated goal-workflow at {destination}")
                return 0

            quarantine = destination.parent / (
                f".goal-workflow.uninstall.{time.time_ns()}.{os.getpid()}"
            )
            os.rename(destination, quarantine)
            try:
                updater.remove_path(quarantine)
            except OSError as exc:
                if not updater.path_exists(destination) and updater.path_exists(quarantine):
                    os.rename(quarantine, destination)
                raise updater.UpdateError(
                    f"could not remove quarantined installation {quarantine}: {exc}"
                ) from exc
            for message in recovery_messages:
                print(message)
            print(f"Uninstalled goal-workflow from {destination}")
        return 0
    except (OSError, updater.UpdateError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
