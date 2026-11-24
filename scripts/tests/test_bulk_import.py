import sys
import tempfile
import unittest
from unittest import mock

from click.testing import CliRunner

sys.path.insert(0, "scripts")

import bulk_import
from helper_functions import manifest_io


class TestParseS3Uri(unittest.TestCase):
    def test_extracts_bucket_and_object_key(self):
        self.assertEqual(
            bulk_import.parse_s3_uri("s3://my-bucket/my-prefix/file.txt"),
            ("my-bucket", "my-prefix/file.txt"),
        )

    def test_rejects_non_s3_uri(self):
        with self.assertRaises(bulk_import.click.BadParameter):
            bulk_import.parse_s3_uri("my-prefix/file.txt")

    def test_rejects_uri_without_object_key(self):
        with self.assertRaises(bulk_import.click.BadParameter):
            bulk_import.parse_s3_uri("s3://my-bucket")


class TestParseManifest(unittest.TestCase):
    def _parse_manifest(self, boto_client):
        boto3 = mock.Mock()
        boto3.client.return_value = boto_client
        manifest = "aws_s3_path,file_name\ns3://my-bucket/my-prefix/,file.txt\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv") as manifest_file:
            manifest_file.write(manifest)
            manifest_file.flush()
            with mock.patch.dict(sys.modules, {"boto3": boto3}):
                return bulk_import.parse_manifest(manifest_file.name)

    def test_checks_objects_and_returns_volume_relative_keys(self):
        s3 = mock.Mock()

        self.assertEqual(self._parse_manifest(s3), ["my-prefix/file.txt"])
        s3.head_object.assert_called_once_with(
            Bucket="my-bucket", Key="my-prefix/file.txt"
        )

    def test_rejects_missing_objects(self):
        s3 = mock.Mock()
        s3.head_object.side_effect = RuntimeError("not found")

        with self.assertRaisesRegex(ValueError, r"S3 object\(s\) not found"):
            self._parse_manifest(s3)

    def test_reads_github_csv_and_tsv(self):
        boto3 = mock.Mock()
        response = mock.Mock()
        with (
            mock.patch.dict(sys.modules, {"boto3": boto3}),
            mock.patch.object(manifest_io.requests, "get", return_value=response) as get,
            mock.patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}),
        ):
            for ref in ("main", "refs/heads/main"):
                for extension, delimiter in (("csv", ","), ("tsv", "\t")):
                    with self.subTest(ref=ref, extension=extension):
                        response.content = (
                            f"aws_s3_path{delimiter}file_name\n"
                            f"s3://my-bucket/my-prefix/{delimiter}file.txt\n"
                        ).encode()
                        url = f"https://raw.githubusercontent.com/owner/repo/{ref}/manifest.{extension}"
                        self.assertEqual(
                            bulk_import.parse_manifest(url), ["my-prefix/file.txt"]
                        )
                        get.assert_called_with(
                            url,
                            headers={"Authorization": "Bearer test-token"},
                            timeout=30,
                        )
        boto3.client.return_value.head_object.assert_called_with(
            Bucket="my-bucket", Key="my-prefix/file.txt"
        )

    def test_reads_local_tsv_without_demo(self):
        boto3 = mock.Mock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv") as manifest_file:
            manifest_file.write(
                "aws_s3_path\tfile_name\ns3://my-bucket/my-prefix/\tfile.txt\n"
            )
            manifest_file.flush()
            with (
                mock.patch.dict(sys.modules, {"boto3": boto3}),
                mock.patch.object(bulk_import, "load_input") as load_input,
            ):
                self.assertEqual(
                    bulk_import.parse_manifest(manifest_file.name), ["my-prefix/file.txt"]
                )
                load_input.assert_not_called()

    def test_github_download_failure_prevents_s3_checks(self):
        boto3 = mock.Mock()
        with (
            mock.patch.dict(sys.modules, {"boto3": boto3}),
            mock.patch.object(
                manifest_io.requests,
                "get",
                side_effect=manifest_io.requests.HTTPError("404"),
            ),
        ):
            with self.assertRaisesRegex(
                bulk_import.click.ClickException, "Could not download manifest"
            ):
                bulk_import.parse_manifest(
                    "https://raw.githubusercontent.com/owner/repo/main/manifest.tsv"
                )
        boto3.client.assert_not_called()


class TestBulkImportCLI(unittest.TestCase):
    def test_s3_keys_file_does_not_require_manifest(self):
        api = mock.Mock()
        with (
            mock.patch.object(bulk_import.hf, "parse_config", return_value=api),
            mock.patch.object(
                bulk_import.hf, "parse_project", return_value="owner/project"
            ),
            mock.patch.object(bulk_import, "parse_manifest") as parse_manifest,
        ):
            with tempfile.NamedTemporaryFile(mode="w") as keys_file:
                keys_file.write("my-prefix/file.txt\n")
                keys_file.flush()
                result = CliRunner().invoke(
                    bulk_import.bulk_import,
                    [
                        "--project", "owner/project",
                        "--volume", "owner/volume",
                        "--s3-keys-file", keys_file.name,
                    ],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Loading 1 S3 key(s).", result.output)
        self.assertIn("[dry-run] Nothing was submitted.", result.output)
        parse_manifest.assert_not_called()
        api.imports.bulk_submit.assert_not_called()
