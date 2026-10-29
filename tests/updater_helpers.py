#!/usr/bin/env python3
"""Exercise updater URL parsing and bounded download behavior."""

from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
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
    def __init__(self, payload: bytes, *, content_length: bool = True) -> None:
        self.payload = payload
        self.headers = {"Content-Length": str(len(payload))} if content_length else {}

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if not self.payload:
            return b""
        chunk, self.payload = self.payload[:size], self.payload[size:]
        return chunk


def archive_payload(entries: dict[str, bytes] | None = None) -> bytes:
    output = BytesIO()
    if entries is None:
        entries = {"repo-master/skills/goal-workflow/SKILL.md": b"skill"}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


class UpdaterHelperTests(unittest.TestCase):
    def test_source_refs(self) -> None:
        self.assertEqual(UPDATER.parse_source_url(UPDATER.DEFAULT_URL, None)[2], "master")
        sha = "a" * 40
        self.assertEqual(UPDATER.parse_source_url(UPDATER.DEFAULT_URL, sha)[2], sha)
        with self.assertRaises(UPDATER.UpdateError):
            UPDATER.parse_source_url(UPDATER.DEFAULT_URL, "x" * 40)

    def test_download_retries_and_extracts_the_actual_payload(self) -> None:
        payload = archive_payload()
        with (
            patch.object(UPDATER, "urlopen", side_effect=[URLError("temporary"), Response(payload)]) as request,
            patch.object(UPDATER.time, "sleep"),
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            source = UPDATER.download_repository("owner", "repo", "master", Path(temp_dir))
            self.assertEqual((source / "skills/goal-workflow/SKILL.md").read_bytes(), b"skill")
            self.assertEqual(request.call_count, 2)

    def test_compressed_size_limit_with_and_without_content_length(self) -> None:
        payload = archive_payload()
        for content_length in (True, False):
            with (
                self.subTest(content_length=content_length),
                patch.object(UPDATER, "MAX_ARCHIVE_BYTES", len(payload) - 1),
                patch.object(UPDATER, "urlopen", return_value=Response(payload, content_length=content_length)),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                with self.assertRaisesRegex(UPDATER.UpdateError, "size limit"):
                    UPDATER.download_repository("owner", "repo", "master", Path(temp_dir))
                self.assertFalse((Path(temp_dir) / "repository").exists())

    def assert_rejected_before_extraction(self, entries: dict[str, bytes], message: str) -> None:
        with (
            patch.object(UPDATER, "urlopen", return_value=Response(archive_payload(entries))),
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            with self.assertRaisesRegex(UPDATER.UpdateError, message):
                UPDATER.download_repository("owner", "repo", "master", Path(temp_dir))
            self.assertEqual(list((Path(temp_dir) / "repository").iterdir()), [])

    def test_high_compression_ratio_cannot_bypass_expanded_size_limit(self) -> None:
        entries = {"repo-master/large.bin": bytes(64 * 1024)}
        self.assertLess(len(archive_payload(entries)), 1024)
        with patch.object(UPDATER, "MAX_EXTRACTED_BYTES", 1024):
            self.assert_rejected_before_extraction(entries, "expanded.*size limit")

    def test_expanded_size_limit_is_cumulative(self) -> None:
        with patch.object(UPDATER, "MAX_EXTRACTED_BYTES", 1024):
            self.assert_rejected_before_extraction(
                {"repo-master/one.bin": bytes(600), "repo-master/two.bin": bytes(600)},
                "expanded.*size limit",
            )

    def test_member_count_limit_includes_empty_directories(self) -> None:
        with patch.object(UPDATER, "MAX_ARCHIVE_MEMBERS", 2):
            self.assert_rejected_before_extraction(
                {f"repo-master/empty-{index}/": b"" for index in range(3)}, "too many entries"
            )

    def test_exact_expanded_size_and_member_count_limits_are_accepted(self) -> None:
        entries = {"repo-master/one.bin": bytes(600), "repo-master/two.bin": bytes(424)}
        with (
            patch.object(UPDATER, "MAX_EXTRACTED_BYTES", 1024),
            patch.object(UPDATER, "MAX_ARCHIVE_MEMBERS", 2),
            patch.object(UPDATER, "urlopen", return_value=Response(archive_payload(entries))),
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            source = UPDATER.download_repository("owner", "repo", "master", Path(temp_dir))
            self.assertEqual((source / "one.bin").read_bytes(), bytes(600))
            self.assertEqual((source / "two.bin").read_bytes(), bytes(424))

    def test_unsafe_paths_and_multiple_roots_are_rejected_before_extraction(self) -> None:
        self.assert_rejected_before_extraction({"../../escape": b"unsafe"}, "unsafe path")
        self.assert_rejected_before_extraction(
            {"first/one": b"one", "second/two": b"two"}, "unexpected layout"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
