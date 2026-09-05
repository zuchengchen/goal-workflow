#!/usr/bin/env python3
"""Install or update goal-workflow from a repository root URL.

The updater is independent of Codex's system skill-installer. It validates the
downloaded bundle without executing downloaded repository code, performs a
cross-platform staged replacement, and protects the target with a lock.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import zipfile


DEFAULT_URL = "https://github.com/zuchengchen/goal-workflow"
DEFAULT_REF = "master"
SKILL_NAME = "goal-workflow"
EXPECTED_BUNDLE_FILES = {"SKILL.md", "agents/openai.yaml"}
FULL_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
DOWNLOAD_RETRIES = 3
DOWNLOAD_CHUNK_BYTES = 64 * 1024
LOCK_NAME = ".goal-workflow.update.lock"
LOCK_TIMEOUT_SECONDS = 120
LOCK_STALE_SECONDS = 3600
RETRYABLE_HTTP_CODES = {408, 425, 429, 500, 502, 503, 504}


class UpdateError(Exception):
    """An expected updater failure that should be shown without a traceback."""


def _decode_scalar(raw: str) -> str:
    value = raw.strip()
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise UpdateError(f"invalid quoted metadata value: {value}") from exc
        if not isinstance(parsed, str):
            raise UpdateError("metadata values must be strings")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise UpdateError(f"invalid quoted metadata value: {value}")
        return value[1:-1].replace("''", "'")
    return value


def _parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UpdateError(f"could not read {path}: {exc}") from exc
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise UpdateError(f"{path} must start with YAML frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise UpdateError(f"{path} has no closing YAML frontmatter delimiter") from exc

    metadata: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        match = re.fullmatch(r"([a-z][a-z0-9_-]*):\s*(.+)", line)
        if not match:
            raise UpdateError(f"unsupported frontmatter syntax in {path}: {line!r}")
        key, raw_value = match.groups()
        if key in metadata:
            raise UpdateError(f"duplicate frontmatter key in {path}: {key}")
        metadata[key] = _decode_scalar(raw_value)
    return metadata, "\n".join(lines[closing + 1 :])


def _parse_agent_metadata(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise UpdateError(f"could not read {path}: {exc}") from exc
    meaningful = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not meaningful or meaningful[0] != "interface:":
        raise UpdateError(f"{path} must contain a top-level interface mapping")
    values: dict[str, str] = {}
    for line in meaningful[1:]:
        if "\t" in line:
            raise UpdateError(f"tabs are not allowed in {path}")
        match = re.fullmatch(r"  ([a-z][a-z0-9_]*):\s*(.+)", line)
        if not match:
            raise UpdateError(f"unsupported metadata syntax in {path}: {line!r}")
        key, raw_value = match.groups()
        if key in values:
            raise UpdateError(f"duplicate metadata key in {path}: {key}")
        values[key] = _decode_scalar(raw_value)
    return values


def validate_bundle(skill: Path, *, identity_only: bool = False) -> None:
    if (not identity_only and skill.name != SKILL_NAME) or not skill.is_dir() or skill.is_symlink():
        raise UpdateError(f"invalid {SKILL_NAME} skill directory: {skill}")

    all_entries = list(skill.rglob("*"))
    if any(entry.is_symlink() for entry in all_entries):
        raise UpdateError(f"symbolic links are not allowed in the skill bundle: {skill}")
    skill_md = skill / "SKILL.md"
    metadata, _ = _parse_frontmatter(skill_md)
    if set(metadata) != {"name", "description"}:
        raise UpdateError(f"{skill_md} frontmatter must contain only name and description")
    if metadata.get("name") != SKILL_NAME:
        raise UpdateError(f"{skill_md} frontmatter name must be {SKILL_NAME}")
    description = metadata.get("description", "")
    if not 1 <= len(description) <= 1024 or "$goal-workflow" not in description:
        raise UpdateError(f"{skill_md} has an invalid description")
    if identity_only:
        return

    files = {
        entry.relative_to(skill).as_posix()
        for entry in all_entries
        if entry.is_file()
    }
    if files != EXPECTED_BUNDLE_FILES:
        raise UpdateError(
            f"canonical skill bundle must contain exactly {sorted(EXPECTED_BUNDLE_FILES)}; "
            f"got {sorted(files)}"
        )
    agent_metadata = _parse_agent_metadata(skill / "agents" / "openai.yaml")
    if set(agent_metadata) != {"display_name", "short_description", "default_prompt"}:
        raise UpdateError(f"{skill}/agents/openai.yaml has invalid interface keys")
    if not 1 <= len(agent_metadata["display_name"]) <= 64:
        raise UpdateError("agent display_name has an invalid length")
    if not 25 <= len(agent_metadata["short_description"]) <= 64:
        raise UpdateError("agent short_description has an invalid length")
    default_prompt = agent_metadata["default_prompt"]
    if not 20 <= len(default_prompt) <= 1024 or "$goal-workflow" not in default_prompt:
        raise UpdateError("agent default_prompt is invalid")


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
    if len(ref) == 40 and FULL_SHA_RE.fullmatch(ref) is None:
        raise UpdateError("a 40-character source ref must be a hexadecimal commit SHA")
    return owner, repo, ref


def _download_once(request: Request, archive_path: Path) -> None:
    with urlopen(request, timeout=30) as response:
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > MAX_ARCHIVE_BYTES:
                    raise UpdateError("downloaded repository archive exceeds the size limit")
            except ValueError:
                pass
        total = 0
        with archive_path.open("wb") as output:
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise UpdateError("downloaded repository archive exceeds the size limit")
                output.write(chunk)


def download_repository(owner: str, repo: str, ref: str, target: Path) -> Path:
    archive_url = f"https://codeload.github.com/{owner}/{repo}/zip/{quote(ref, safe='')}"
    archive_path = target / "repository.zip"
    request = Request(archive_url, headers={"User-Agent": "goal-workflow-updater"})
    last_error: Exception | None = None
    for attempt in range(DOWNLOAD_RETRIES):
        try:
            if archive_path.exists():
                archive_path.unlink()
            _download_once(request, archive_path)
            break
        except UpdateError:
            raise
        except HTTPError as exc:
            last_error = exc
            if exc.code not in RETRYABLE_HTTP_CODES:
                raise UpdateError(f"could not download {archive_url}: HTTP {exc.code}") from exc
        except (OSError, URLError, TimeoutError) as exc:
            last_error = exc
        if attempt + 1 < DOWNLOAD_RETRIES:
            time.sleep(0.5 * (2**attempt))
    else:
        raise UpdateError(
            f"could not download {archive_url} after {DOWNLOAD_RETRIES} attempts: {last_error}"
        )

    root = target / "repository"
    root.mkdir()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            root_real = root.resolve()
            members = archive.infolist()
            for member in members:
                member_path = (root / member.filename).resolve()
                if member_path != root_real and root_real not in member_path.parents:
                    raise UpdateError("downloaded archive contains an unsafe path")
            archive.extractall(root)
            top_levels = {member.filename.split("/", 1)[0] for member in members}
    except (zipfile.BadZipFile, OSError) as exc:
        raise UpdateError(f"downloaded repository archive is invalid: {exc}") from exc

    top_levels.discard("")
    if len(top_levels) != 1:
        raise UpdateError("downloaded repository archive has an unexpected layout")
    return root / next(iter(top_levels))


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
    candidates = [destination, Path.home() / ".agents" / "skills" / SKILL_NAME]
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


def path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def is_goal_skill(path: Path) -> bool:
    try:
        if path.is_symlink():
            path = path.resolve(strict=True)
        validate_bundle(path, identity_only=True)
        return True
    except (OSError, UpdateError):
        return False


def duplicate_installations(destination: Path) -> list[Path]:
    return [
        path
        for path in candidate_duplicate_paths(destination)
        if path != destination and path_exists(path) and is_goal_skill(path)
    ]


def prune_duplicates(paths: list[Path]) -> None:
    for path in paths:
        try:
            remove_path(path)
        except OSError as exc:
            raise UpdateError(f"could not remove duplicate installation {path}: {exc}") from exc


class UpdateLock:
    def __init__(self, parent: Path) -> None:
        self.parent = parent
        self.path = parent / LOCK_NAME
        self.owner_path = self.path / "owner.json"
        self.token = f"{os.getpid()}-{time.time_ns()}"
        self.acquired = False

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except PermissionError:
            return True
        except ProcessLookupError:
            return False
        except OSError:
            return False
        return True

    def _is_stale(self) -> bool:
        try:
            if self.path.is_symlink():
                return False
            if not self.path.is_dir():
                return time.time() - self.path.stat().st_mtime >= LOCK_STALE_SECONDS
            age = time.time() - self.path.stat().st_mtime
            if age < LOCK_STALE_SECONDS:
                return False
            owner = json.loads(self.owner_path.read_text(encoding="utf-8"))
            return not self._pid_alive(int(owner.get("pid", 0)))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            try:
                return time.time() - self.path.stat().st_mtime >= LOCK_STALE_SECONDS
            except OSError:
                # The lock may have been removed by its owner between the
                # failed read and this check; let the acquisition loop retry.
                return False

    def __enter__(self) -> "UpdateLock":
        try:
            self.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise UpdateError(f"could not create lock parent: {exc}") from exc
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                self.path.mkdir()
                try:
                    self.owner_path.write_text(
                        json.dumps({"pid": os.getpid(), "token": self.token}),
                        encoding="utf-8",
                    )
                except OSError as exc:
                    try:
                        shutil.rmtree(self.path)
                    except OSError:
                        pass
                    raise UpdateError(f"could not initialize update lock: {exc}") from exc
                self.acquired = True
                return self
            except FileExistsError:
                if self.path.is_symlink():
                    raise UpdateError(f"update lock path is a symbolic link: {self.path}")
                if self._is_stale():
                    try:
                        if self.path.is_dir():
                            shutil.rmtree(self.path)
                        else:
                            self.path.unlink()
                    except OSError as exc:
                        raise UpdateError(f"could not remove stale update lock: {exc}") from exc
                    continue
                if time.monotonic() >= deadline:
                    raise UpdateError(
                        f"another goal-workflow update is in progress: {self.path}"
                    )
                time.sleep(0.25)
            except OSError as exc:
                raise UpdateError(f"could not acquire update lock: {exc}") from exc

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        if not self.acquired:
            return
        try:
            owner = json.loads(self.owner_path.read_text(encoding="utf-8"))
            if owner.get("token") == self.token:
                shutil.rmtree(self.path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        self.acquired = False


def recover_interrupted_update(destination: Path) -> list[str]:
    parent = destination.parent
    if not parent.exists():
        return []
    install_paths = sorted(parent.glob(".goal-workflow.install.*"))
    replace_paths = sorted(parent.glob(".goal-workflow.replace.*"))
    messages: list[str] = []

    if not path_exists(destination):
        valid_replacements = [
            path
            for path in replace_paths
            if path.is_dir() and not path.is_symlink() and is_goal_skill(path)
        ]
        if len(valid_replacements) > 1:
            raise UpdateError(
                "multiple recoverable interrupted installations found; inspect "
                + ", ".join(str(path) for path in valid_replacements)
            )
        if valid_replacements:
            try:
                os.rename(valid_replacements[0], destination)
            except OSError as exc:
                raise UpdateError(
                    f"could not recover interrupted installation {valid_replacements[0]}: {exc}"
                ) from exc
            replace_paths.remove(valid_replacements[0])
            messages.append(f"Recovered interrupted installation at {destination}")

    for path in replace_paths:
        if not path_exists(path):
            continue
        if not is_goal_skill(path):
            raise UpdateError(f"unrecognized replacement residue requires review: {path}")
        try:
            remove_path(path)
        except OSError as exc:
            raise UpdateError(f"could not remove replacement residue {path}: {exc}") from exc
        messages.append(f"Removed interrupted replacement residue: {path}")
    for path in install_paths:
        if path_exists(path):
            try:
                remove_path(path)
            except OSError as exc:
                raise UpdateError(f"could not remove staging residue {path}: {exc}") from exc
            messages.append(f"Removed interrupted staging residue: {path}")
    return messages


def install_bundle(source: Path, destination: Path) -> None:
    source_skill = source / "skills" / SKILL_NAME
    validate_bundle(source_skill)
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
        validate_bundle(destination, identity_only=True)

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
        validate_bundle(staged_skill)
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
            try:
                remove_path(stage_root)
            except OSError as cleanup_exc:
                if sys.exc_info()[0] is None:
                    raise UpdateError(
                        f"could not remove staging directory {stage_root}: {cleanup_exc}"
                    ) from cleanup_exc


def resolve_source(
    source_dir: str | None, url: str, ref: str | None, temp_dir: Path
) -> tuple[Path, str | None]:
    if source_dir:
        try:
            source = Path(source_dir).expanduser().resolve()
        except OSError as exc:
            raise UpdateError(f"could not resolve source directory: {exc}") from exc
        if not source.is_dir():
            raise UpdateError(f"source directory does not exist: {source}")
        return source, None

    owner, repo, source_ref = parse_source_url(url, ref)
    return download_repository(owner, repo, source_ref, temp_dir), source_ref


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or update goal-workflow from its GitHub repository root."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="repository root URL")
    parser.add_argument("--ref", help="branch, tag, or commit; defaults to master")
    parser.add_argument(
        "--require-immutable-ref",
        action="store_true",
        help="require --ref or the URL ref to be a full 40-character commit SHA",
    )
    parser.add_argument(
        "--source-dir",
        help="use an existing repository checkout instead of downloading the URL",
    )
    parser.add_argument("--dest", help="single user skill destination")
    duplicate_group = parser.add_mutually_exclusive_group()
    duplicate_group.add_argument(
        "--prune-duplicates",
        action="store_true",
        help="explicitly request the default duplicate cleanup behavior",
    )
    duplicate_group.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="keep validated duplicate installations and report them",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        destination = resolve_destination(args.dest)
        if args.require_immutable_ref and args.source_dir:
            raise UpdateError("--require-immutable-ref requires a GitHub URL, not --source-dir")
        with UpdateLock(destination.parent):
            recovery_messages = recover_interrupted_update(destination)
            duplicates = duplicate_installations(destination)
            if duplicates and args.keep_duplicates:
                print(
                    "Keeping validated duplicate installations:\n"
                    + "\n".join(f"- {path}" for path in duplicates),
                    file=sys.stderr,
                )
            with tempfile.TemporaryDirectory(prefix="goal-workflow-update-") as temp_dir:
                source, source_ref = resolve_source(
                    args.source_dir, args.url, args.ref, Path(temp_dir)
                )
                if args.require_immutable_ref and not source_ref:
                    raise UpdateError("an immutable source ref is required")
                if args.require_immutable_ref and FULL_SHA_RE.fullmatch(source_ref or "") is None:
                    raise UpdateError("--require-immutable-ref requires a full commit SHA")
                install_bundle(source, destination)
            if duplicates and not args.keep_duplicates:
                prune_duplicates(duplicates)
                print(f"Removed {len(duplicates)} duplicate installation(s).")
            for message in recovery_messages:
                print(message)
            ref_message = f" at ref {source_ref}" if source_ref else ""
            print(f"Updated {SKILL_NAME} at {destination}{ref_message}")
        return 0
    except UpdateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
