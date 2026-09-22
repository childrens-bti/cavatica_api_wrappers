import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "scripts")

import bulk_import


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
