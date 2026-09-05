#!/usr/bin/env python3
"""Install or update goal-workflow from the repository root URL.

This updater is intentionally independent of Codex's system skill-installer. It
downloads the repository, validates the canonical bundle, and performs the
no-persistent-backup replacement in Python so it works without a POSIX shell.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import zipfile


DEFAULT_URL = "https://github.com/zuchengchen/goal-workflow"
DEFAULT_REF = "master"
SKILL_NAME = "goal-workflow"


class UpdateError(Exception):
    """An expected updater failure that should be shown without a traceback."""


def parse_source_url(raw_url: str, ref_override: str | None) -> tuple[str, str, str]:
    parsed = urlparse(raw_url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise UpdateError("source URL must be an HTTPS GitHub repository URL")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise UpdateError("source URL must include an owner and repository")
    owner, repo = parts[:2]
    if repo.endswith(".git"):
        repo = repo[:-4]

    if len(parts) == 2:
        url_ref = DEFAULT_REF
    elif len(parts) == 4 and parts[2] == "tree":
        url_ref = parts[3]
    else:
        raise UpdateError(
            "source URL must be the repository root or /tree/<ref>; "
            "do not include a nested skill path"
        )

    ref = ref_override or url_ref
    if not ref or ref in {".", ".."}:
        raise UpdateError("source ref must not be empty")
    return owner, repo, ref


def download_repository(owner: str, repo: str, ref: str, target: Path) -> Path:
    archive_url = (
        f"https://codeload.github.com/{owner}/{repo}/zip/{quote(ref, safe='')}"
    )
    archive_path = target / "repository.zip"
    request = Request(archive_url, headers={"User-Agent": "goal-workflow-updater"})
    try:
        with urlopen(request, timeout=30) as response:
            archive_path.write_bytes(response.read())
    except (HTTPError, OSError, URLError, TimeoutError) as exc:
        raise UpdateError(f"could not download {archive_url}: {exc}") from exc

    root = target / "repository"
    root.mkdir()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            root_real = root.resolve()
            for member in archive.infolist():
                member_path = (root / member.filename).resolve()
                if member_path != root_real and root_real not in member_path.parents:
                    raise UpdateError("downloaded archive contains an unsafe path")
            archive.extractall(root)
            top_levels = {member.filename.split("/", 1)[0] for member in archive.infolist()}
    except (zipfile.BadZipFile, OSError) as exc:
        raise UpdateError(f"downloaded repository archive is invalid: {exc}") from exc

    top_levels.discard("")
    if len(top_levels) != 1:
        raise UpdateError("downloaded repository archive has an unexpected layout")
    return root / next(iter(top_levels))


def validate_source(source: Path) -> None:
    validator = source / "scripts" / "validate.py"
    skill = source / "skills" / SKILL_NAME
    if not validator.is_file() or not skill.is_dir():
        raise UpdateError("source repository does not contain the canonical skill bundle")

    validate_skill(validator, skill, "--installed-only")


def validate_skill(validator: Path, skill: Path, mode: str) -> None:
    try:
        result = subprocess.run(
            [sys.executable, str(validator), "--skill-dir", str(skill), mode],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise UpdateError(f"could not run skill validation: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise UpdateError(f"skill validation failed: {detail}")


def resolve_destination(raw_dest: str | None) -> Path:
    if raw_dest:
        candidate = Path(raw_dest).expanduser()
    else:
        codex_home = os.environ.get("CODEX_HOME")
        base = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
        candidate = base / "skills" / SKILL_NAME

    if candidate.name != SKILL_NAME:
        raise UpdateError(f"destination must be named {SKILL_NAME}: {candidate}")
    if candidate.is_symlink():
        raise UpdateError(f"refusing to update a symbolic-link destination: {candidate}")
    try:
        parent = candidate.parent.resolve()
    except OSError as exc:
        raise UpdateError(f"could not resolve destination parent: {exc}") from exc
    if parent.name != "skills" or parent == parent.parent:
        raise UpdateError(f"destination must be directly inside a skills directory: {candidate}")
    return parent / SKILL_NAME


def candidate_duplicate_paths(destination: Path) -> list[Path]:
    candidates = [destination]
    home_agents = Path.home() / ".agents" / "skills" / SKILL_NAME
    candidates.append(home_agents)

    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        candidates.append(directory / ".agents" / "skills" / SKILL_NAME)

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        normalized = candidate.absolute()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def is_goal_skill(path: Path) -> bool:
    if path.is_symlink():
        try:
            path = path.resolve(strict=True)
        except OSError:
            return False
    if not path.is_dir():
        return False
    skill_md = path / "SKILL.md"
    if not skill_md.is_file():
        return False
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    parts = text.split("---", 2)
    return (
        len(parts) == 3
        and re.search(r"(?m)^name:\s*goal-workflow\s*$", parts[1]) is not None
    )


def duplicate_installations(destination: Path) -> list[Path]:
    return [
        path
        for path in candidate_duplicate_paths(destination)
        if path != destination and path.exists() and is_goal_skill(path)
    ]


def prune_duplicates(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path.is_symlink():
                path.unlink()
            else:
                shutil.rmtree(path)
        except OSError as exc:
            raise UpdateError(f"could not remove duplicate installation {path}: {exc}") from exc


def path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def install_bundle(source: Path, destination: Path) -> None:
    source_skill = source / "skills" / SKILL_NAME
    validator = source / "scripts" / "validate.py"
    if not source_skill.is_dir() or not validator.is_file():
        raise UpdateError("source repository does not contain the canonical skill bundle")

    destination_parent = destination.parent
    try:
        destination_parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UpdateError(f"could not create destination directory: {exc}") from exc
    if destination.is_symlink():
        raise UpdateError(f"refusing to update a symbolic-link destination: {destination}")
    if path_exists(destination):
        if not destination.is_dir():
            raise UpdateError(f"destination exists but is not a directory: {destination}")
        validate_skill(validator, destination, "--identity-only")

    try:
        stage_root = Path(
            tempfile.mkdtemp(prefix=".goal-workflow.install.", dir=destination_parent)
        )
    except OSError as exc:
        raise UpdateError(f"could not create staging directory: {exc}") from exc
    staged_skill = stage_root / SKILL_NAME
    old_path = destination_parent / f".goal-workflow.replace.{os.getpid()}"
    suffix = 0
    while path_exists(old_path):
        suffix += 1
        old_path = destination_parent / f".goal-workflow.replace.{os.getpid()}.{suffix}"

    old_moved = False
    try:
        shutil.copytree(source_skill, staged_skill)
        validate_skill(validator, staged_skill, "--installed-only")

        if path_exists(destination):
            os.rename(destination, old_path)
            old_moved = True
        os.rename(staged_skill, destination)
        if old_moved:
            remove_path(old_path)
            old_moved = False
    except (OSError, UpdateError) as exc:
        if old_moved:
            try:
                if path_exists(destination):
                    remove_path(destination)
                os.rename(old_path, destination)
                old_moved = False
            except OSError as rollback_exc:
                raise UpdateError(
                    f"skill replacement failed and rollback failed; previous installation "
                    f"is at {old_path}: {rollback_exc}"
                ) from rollback_exc
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"skill replacement failed: {exc}") from exc
    finally:
        if path_exists(stage_root):
            remove_path(stage_root)


def resolve_source(source_dir: str | None, url: str, ref: str | None, temp_dir: Path) -> Path:
    if source_dir:
        try:
            source = Path(source_dir).expanduser().resolve()
        except OSError as exc:
            raise UpdateError(f"could not resolve source directory: {exc}") from exc
        if not source.is_dir():
            raise UpdateError(f"source directory does not exist: {source}")
        return source

    owner, repo, source_ref = parse_source_url(url, ref)
    return download_repository(owner, repo, source_ref, temp_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or update goal-workflow from its GitHub repository root."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="repository root URL")
    parser.add_argument("--ref", help="branch, tag, or commit; defaults to master")
    parser.add_argument(
        "--source-dir",
        help="use an existing repository checkout instead of downloading the URL",
    )
    parser.add_argument("--dest", help="single user skill destination")
    parser.add_argument(
        "--prune-duplicates",
        action="store_true",
        help="remove validated duplicate installations after the update",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        destination = resolve_destination(args.dest)
        duplicates = duplicate_installations(destination)
    except UpdateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if duplicates and not args.prune_duplicates:
        paths = "\n".join(f"- {path}" for path in duplicates)
        print(
            "duplicate goal-workflow installations found; rerun with "
            "--prune-duplicates after reviewing:\n" + paths,
            file=sys.stderr,
        )
        return 2

    with tempfile.TemporaryDirectory(prefix="goal-workflow-update-") as temp_dir:
        try:
            source = resolve_source(args.source_dir, args.url, args.ref, Path(temp_dir))
            validate_source(source)
            install_bundle(source, destination)
        except UpdateError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if duplicates and args.prune_duplicates:
        try:
            prune_duplicates(duplicates)
        except UpdateError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Removed {len(duplicates)} duplicate installation(s).")
    print(f"Updated {SKILL_NAME} at {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
