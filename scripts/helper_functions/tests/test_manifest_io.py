"""Tests for shared GitHub/local input loading policies."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import click

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from helper_functions import manifest_io


class TestManifestIO(unittest.TestCase):
    def test_local_input_requires_demo_and_handles_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.tsv"
            path.write_bytes(b"\xef\xbb\xbfBioassay_ID\nBA_12345678\n")
            with self.assertRaisesRegex(click.ClickException, "use --demo"):
                manifest_io.load_input(str(path))
            self.assertEqual(
                manifest_io.load_input(str(path), demo=True),
                "Bioassay_ID\nBA_12345678\n",
            )

    def test_main_and_refs_heads_main_are_allowed(self):
        response = mock.Mock(content=b"organism\nhuman\n")
        with mock.patch.object(manifest_io.requests, "get", return_value=response) as get:
            for branch in ("main", "refs/heads/main"):
                with self.subTest(branch=branch):
                    url = f"https://raw.githubusercontent.com/owner/repo/{branch}/manifest.tsv"
                    self.assertEqual(
                        manifest_io.load_input(url),
                        "organism\nhuman\n",
                    )
            self.assertEqual(get.call_count, 2)

    def test_non_main_inputs_are_rejected_even_in_demo_mode(self):
        with mock.patch.object(manifest_io.requests, "get") as get:
            for branch in ("feature", "master", "refs/heads/feature", "0123456789abcdef"):
                for option in ("--manifest", "--options_file"):
                    for demo in (False, True):
                        with self.subTest(branch=branch, option=option, demo=demo):
                            url = f"https://raw.githubusercontent.com/owner/repo/{branch}/input.tsv"
                            with self.assertRaisesRegex(click.ClickException, "GitHub main branch"):
                                manifest_io.load_input(url, demo=demo, option=option)
            get.assert_not_called()

    def test_dot_segments_are_rejected_for_both_inputs(self):
        with mock.patch.object(manifest_io.requests, "get") as get:
            for path in ("main/../feature", "main/%2e%2e/feature", "main/%252e%252e/feature"):
                for option in ("--manifest", "--options_file"):
                    with self.subTest(path=path, option=option):
                        url = f"https://raw.githubusercontent.com/owner/repo/{path}/input.tsv"
                        with self.assertRaisesRegex(click.ClickException, "dot path segments"):
                            manifest_io.load_input(url, option=option)
            get.assert_not_called()

    def test_invalid_github_inputs_fail_before_download(self):
        urls = (
            "https://github.com/owner/repo/blob/main/options.tsv",
            "http://raw.githubusercontent.com/owner/repo/main/options.tsv",
            "https://raw.githubusercontent.com/owner/repo/main/options.tsv?token=example",
            "https://raw.githubusercontent.com/owner/repo/main/options.tsv#fragment",
        )
        with mock.patch.object(manifest_io.requests, "get") as get:
            for url in urls:
                with self.subTest(url=url):
                    with self.assertRaises(click.ClickException):
                        manifest_io.load_input(url, option="--options_file")
            get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
