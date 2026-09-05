#!/usr/bin/env python3
"""Exercise updater URL parsing and bounded download behavior."""

from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import sys
import tempfile
from urllib.error import URLError
import zipfile


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "goal_workflow_updater", ROOT / "scripts" / "update-installed-skill.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load updater")
UPDATER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATER)


class Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if not self.payload:
            return b""
        chunk, self.payload = self.payload[:size], self.payload[size:]
        return chunk


def archive_payload() -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("repo-master/skills/goal-workflow/SKILL.md", "skill")
    return output.getvalue()


def main() -> int:
    assert UPDATER.parse_source_url(UPDATER.DEFAULT_URL, None)[2] == "master"
    sha = "a" * 40
    assert UPDATER.parse_source_url(UPDATER.DEFAULT_URL, sha)[2] == sha
    try:
        UPDATER.parse_source_url(UPDATER.DEFAULT_URL, "x" * 40)
    except UPDATER.UpdateError:
        pass
    else:
        raise AssertionError("invalid full SHA was accepted")

    payload = archive_payload()
    attempts = 0

    def flaky(_request: object, timeout: int) -> Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise URLError("temporary network failure")
        return Response(payload)

    UPDATER.urlopen = flaky
    with tempfile.TemporaryDirectory() as temp_dir:
        source = UPDATER.download_repository("owner", "repo", "master", Path(temp_dir))
        assert source.is_dir()
    assert attempts == 2

    UPDATER.MAX_ARCHIVE_BYTES = len(payload) - 1
    UPDATER.urlopen = lambda _request, timeout: Response(payload)
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            UPDATER.download_repository("owner", "repo", "master", Path(temp_dir))
        except UPDATER.UpdateError as exc:
            assert "size limit" in str(exc)
        else:
            raise AssertionError("oversized archive was accepted")

    print("Updater helper contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
