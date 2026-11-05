"""CLI coverage using synthetic manifests and mocked CAVATICA/GitHub calls."""

from contextlib import nullcontext
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import requests
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import task_validator as script
from helper_functions import manifest_io


BAID_A = "BA_12345678"
BAID_B = "BA_ABCDEFGH"
BAID_EXTRA = "BA_87654321"
MANIFEST_URL = "https://raw.githubusercontent.com/owner/repo/main/cohort.tsv"
OPTIONS_URL = "https://raw.githubusercontent.com/owner/repo/main/options.tsv"


def task(baid, status="DRAFT"):
    return SimpleNamespace(name=f"rna_workflow_20261105_{baid}", status=status)


class TestTaskValidator(unittest.TestCase):
    def invoke(
        self, manifest, tasks, task_file=None, demo=False, local=False,
        options=None, options_local=False, options_error=None,
        credentials_error=None, read_error=None,
    ):
        api = mock.Mock()

        def fetch(id):
            value = tasks[id]
            if isinstance(value, Exception):
                raise value
            return value

        api.tasks.get.side_effect = fetch
        options = options if options is not None else f"output_basename\n{BAID_A}\n"

        def get_input(url, **kwargs):
            if url == OPTIONS_URL and options_error:
                raise options_error
            content = {MANIFEST_URL: manifest, OPTIONS_URL: options}[url]
            response = mock.Mock()
            response.content = content.encode("utf-8")
            return response
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("tasks.txt").write_text(
                task_file if task_file is not None else "\n".join(tasks) + "\n",
                encoding="utf-8",
            )
            Path("manifest.tsv").write_text(manifest, encoding="utf-8")
            Path("options.tsv").write_text(
                options,
                encoding="utf-8",
            )
            args = [
                "--profile", "test", "--task_file", "tasks.txt",
                "--manifest", "manifest.tsv" if local else MANIFEST_URL,
                "--options_file", "options.tsv" if options_local else OPTIONS_URL,
            ]
            if demo:
                args.append("--demo")
            with (
                mock.patch.object(
                    script.hf, "parse_config", return_value=api, side_effect=credentials_error,
                ) as config,
                mock.patch.object(manifest_io.requests, "get", side_effect=get_input) as download,
                mock.patch.dict(manifest_io.os.environ, {}, clear=True),
            ):
                with (
                    mock.patch("builtins.open", side_effect=read_error)
                    if read_error else nullcontext()
                ):
                    result = runner.invoke(script.task_validator, args)
                self.assertEqual(
                    result.output.splitlines()[-1],
                    "Validation passed." if result.exit_code == 0 else "Validation failed.",
                    result.output,
                )
        return result, api, config, download

    def test_whole_cohort_passes(self):
        manifest = (
            f"Bioassay_ID\tfile_name\n{BAID_A}\tr1.fastq\n{BAID_A}\tr2.fastq\n"
            f"{BAID_B}\tr1.fastq\n{BAID_B}\tr2.fastq\n"
        )
        result, api, config, download = self.invoke(
            manifest, {"first": task(BAID_A), "second": task(BAID_B)},
            task_file="\ufeff first \n\nsecond\n",
            options=f"output_basename\n{BAID_A}\n{BAID_B}\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("2 unique options BAIDs and 2 unique manifest BAIDs; 2 BAIDs matched", result.output)
        self.assertIn("Validation passed", result.output)
        self.assertNotIn("WARNING", result.output)
        config.assert_called_once_with("test")
        api.tasks.get.assert_has_calls([mock.call(id="first"), mock.call(id="second")])
        self.assertEqual(api.tasks.get.call_count, 2)
        download.assert_has_calls([
            mock.call(MANIFEST_URL, headers={}, timeout=30),
            mock.call(OPTIONS_URL, headers={}, timeout=30),
        ])
        self.assertEqual(download.call_count, 2)

    def test_non_draft_tasks_fail(self):
        for status in ("QUEUED", "RUNNING", "COMPLETED", "FAILED", "ABORTED"):
            with self.subTest(status=status):
                result, _, _, _ = self.invoke(
                    f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A, status)},
                )
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertIn(f"Task is not DRAFT (status: {status}): first", result.output)
                self.assertNotIn("Missing BAID", result.output)

    def test_rerun_options_file_passes(self):
        # Only BAID_B is being rerun; the original cohort also had BAID_A.
        options = (
            "input_reads\tsample_name\toutput_basename\tapp\n"
            f"rerun.fastq\t{BAID_B}\t{BAID_B}\towner/project/rna/1\n"
        )
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"rerun": task(BAID_B)}, options=options,
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1 unique options BAIDs and 2 unique manifest BAIDs; 1 BAIDs matched", result.output)
        self.assertIn("WARNING: Options file contains 1 of 2 manifest samples", result.output)
        self.assertNotIn("Missing BAID", result.output)
        self.assertIn("Validation passed", result.output)

    def test_malformed_options_files_fail_before_api_setup(self):
        cases = [
            ("sample_name\tapp\nsample\towner/project/rna/1\n", "output_basename"),
            ("output_basename\tapp\n\towner/project/rna/1\n", "output_basename contains no BAID: ''"),
            ("output_basename\nnot-a-baid\n", "output_basename contains no BAID: 'not-a-baid'"),
            (f"output_basename\tapp\n{BAID_B}\n", "wrong number of columns"),
            (f"output_basename\tapp\n{BAID_B}\tapp\textra\n", "wrong number of columns"),
            ("output_basename\n", "Options file contains no BAIDs"),
            (f'output_basename\tapp\n{BAID_B}\t"unterminated\n', "Unable to read input files"),
        ]
        for options, message in cases:
            with self.subTest(options=options):
                result, api, config, _ = self.invoke(
                    f"Bioassay_ID\n{BAID_B}\n", {"rerun": task(BAID_B)}, options=options,
                )
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn(message, result.output)
                config.assert_not_called()
                api.tasks.get.assert_not_called()

    def test_extracts_baids_from_prefixed_and_suffixed_output_basenames(self):
        for basename in (f"rerun_{BAID_A}", f"{BAID_A}_corrected", f"rerun_{BAID_A}_corrected"):
            with self.subTest(basename=basename):
                result, _, _, _ = self.invoke(
                    f"Bioassay_ID\n{BAID_A}\n", {"first": task(basename)},
                    options=f"output_basename\n{basename}\n",
                )
                self.assertEqual(result.exit_code, 0, result.output)

    def test_multiple_baids_in_one_output_basename_and_task_pass(self):
        basename = f"paired_{BAID_A}_{BAID_B}_rerun"
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n", {"paired": task(basename)},
            options=f"output_basename\n{basename}\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("2 unique options BAIDs and 2 unique manifest BAIDs; 2 BAIDs matched", result.output)

    def test_two_tumors_sharing_one_normal_pass(self):
        first_pair = f"{BAID_A}_{BAID_B}"
        second_pair = f"{BAID_EXTRA}_{BAID_B}"
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n{BAID_EXTRA}\n",
            {"first": task(first_pair), "second": task(second_pair)},
            options=f"output_basename\n{first_pair}\n{second_pair}\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Matched 2 of 2 options rows.", result.output)
        self.assertNotIn("WARNING", result.output)

    def test_dropped_normal_in_one_pair_fails_even_when_other_task_has_it(self):
        first_pair = f"{BAID_A}_{BAID_B}"
        second_pair = f"{BAID_EXTRA}_{BAID_B}"
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n{BAID_EXTRA}\n",
            {"first": task(first_pair), "second": task(BAID_EXTRA)},
            options=f"output_basename\n{first_pair}\n{second_pair}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn(f"No task for options row: {BAID_EXTRA}_{BAID_B}", result.output)
        self.assertIn("Task does not match an options row", result.output)
        self.assertIn("Matched 1 of 2 options rows.", result.output)
        self.assertNotIn("Missing BAID", result.output)

    def test_wrong_pairings_fail_even_when_pooled_baids_match(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n{BAID_EXTRA}\n",
            {"paired": task(f"{BAID_A}_{BAID_EXTRA}"), "normal": task(BAID_B)},
            options=f"output_basename\n{BAID_A}_{BAID_B}\n{BAID_EXTRA}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("No task for options row", result.output)
        self.assertIn("Task does not match an options row", result.output)
        self.assertIn("Matched 0 of 2 options rows.", result.output)
        self.assertNotIn("Missing BAID", result.output)

    def test_baid_order_within_pair_does_not_affect_matching(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"paired": task(f"{BAID_B}_{BAID_A}")},
            options=f"output_basename\n{BAID_A}_{BAID_B}\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Matched 1 of 1 options rows.", result.output)

    def test_duplicate_options_rows_require_one_task_each(self):
        pair = f"{BAID_A}_{BAID_B}"
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n", {"paired": task(pair)},
            options=f"output_basename\n{pair}\n{pair}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn(f"No task for options row: {pair} (missing 1 of 2 tasks)", result.output)
        self.assertIn("Matched 1 of 2 options rows.", result.output)

    def test_matching_duplicate_options_rows_warn_and_pass(self):
        pair = f"{BAID_A}_{BAID_B}"
        result, api, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"first": task(pair), "second": task(pair)},
            options=f"output_basename\n{pair}\n{pair}\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Matched 2 of 2 options rows.", result.output)
        self.assertIn(f"WARNING: Duplicate options row BAID set: {pair}", result.output)
        self.assertEqual(api.tasks.get.call_count, 2)

    def test_single_baid_tasks_cannot_replace_one_paired_options_row(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"first": task(BAID_A), "second": task(BAID_B)},
            options=f"output_basename\n{BAID_A}_{BAID_B}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("No task for options row", result.output)
        self.assertIn("Matched 0 of 1 options rows.", result.output)
        self.assertNotIn("Missing BAID", result.output)

    def test_repeated_baid_within_basename_is_counted_once(self):
        basename = f"{BAID_A}_rerun_{BAID_A}"
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(basename)},
            options=f"output_basename\n{basename}\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1 unique options BAIDs", result.output)

    def test_partial_baids_in_output_basename_are_rejected(self):
        for basename in (f"{BAID_A}9", f"x{BAID_A}"):
            with self.subTest(basename=basename):
                result, api, config, _ = self.invoke(
                    f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A)},
                    options=f"output_basename\n{basename}\n",
                )
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn("output_basename contains no BAID", result.output)
                config.assert_not_called()
                api.tasks.get.assert_not_called()

    def test_all_baids_extracted_from_basename_must_have_tasks(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n", {"first": task(BAID_A)},
            options=f"output_basename\npaired_{BAID_A}_{BAID_B}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn(f"Missing BAID (options sample has no retrieved task): {BAID_B}", result.output)

    def test_extracted_baid_outside_manifest_fails(self):
        basename = f"paired_{BAID_A}_{BAID_EXTRA}_rerun"
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"paired": task(basename)},
            options=f"output_basename\n{basename}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn(f"Options BAID not in manifest: {BAID_EXTRA}", result.output)

    def test_one_sample_rerun_from_37_sample_cohort_warns_and_passes(self):
        baids = [f"BA_{index:08d}" for index in range(37)]
        result, api, _, _ = self.invoke(
            "Bioassay_ID\n" + "\n".join(baids) + "\n",
            {"rerun": task(baids[12])},
            options=f"output_basename\n{baids[12]}\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            result.output,
            "Checked 1 unique task IDs against 1 unique options BAIDs and "
            "37 unique manifest BAIDs; 1 BAIDs matched.\n"
            "Matched 1 of 1 options rows.\n"
            "WARNING: Options file contains 1 of 37 manifest samples; "
            "36 manifest samples are not included in this run.\n"
            "Validation passed.\n",
        )
        api.tasks.get.assert_called_once_with(id="rerun")

    def test_options_and_tasks_matching_outside_cohort_fail(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"extra": task(BAID_EXTRA)},
            options=f"output_basename\n{BAID_EXTRA}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn(f"Options BAID not in manifest: {BAID_EXTRA}", result.output)
        self.assertIn(f"Task BAID not in manifest {BAID_EXTRA}", result.output)
        self.assertNotIn("WARNING", result.output)

    def test_cohort_task_not_in_rerun_options_fails(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"first": task(BAID_A), "extra": task(BAID_B)},
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn(f"Unexpected BAID {BAID_B} (not in options file)", result.output)
        self.assertNotIn("WARNING", result.output)

    def test_subset_options_with_missing_task_fail(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n{BAID_EXTRA}\n",
            {"first": task(BAID_A)},
            options=f"output_basename\n{BAID_A}\n{BAID_B}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn(f"Missing BAID (options sample has no retrieved task): {BAID_B}", result.output)
        self.assertNotIn(f"Missing BAID (options sample has no retrieved task): {BAID_EXTRA}", result.output)
        self.assertNotIn("WARNING", result.output)

    def test_subset_warning_does_not_allow_non_draft_task(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n", {"first": task(BAID_A, "COMPLETED")},
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Task is not DRAFT", result.output)
        self.assertNotIn("WARNING", result.output)

    def test_duplicate_task_id_is_reported_and_fetched_once(self):
        result, api, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A)},
            task_file="first\n first \n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Duplicate task ID: first (2 entries)", result.output)
        api.tasks.get.assert_called_once_with(id="first")

    def test_unexpected_and_missing_samples_are_both_reported(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"first": task(BAID_A), "extra": task(BAID_EXTRA)},
            options=f"output_basename\n{BAID_A}\n{BAID_B}\n",
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn(f"Unexpected BAID {BAID_EXTRA} (not in options file): extra", result.output)
        self.assertIn(f"Missing BAID (options sample has no retrieved task): {BAID_B}", result.output)

    def test_task_name_without_baid_fails(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task("sample-without-baid")},
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Task name contains no BAID: first", result.output)
        self.assertIn(f"Missing BAID (options sample has no retrieved task): {BAID_A}", result.output)

    def test_task_fetch_failure_does_not_stop_remaining_tasks(self):
        result, api, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"failed": RuntimeError("not found"), "second": task(BAID_B)},
            options=f"output_basename\n{BAID_A}\n{BAID_B}\n",
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("Unable to retrieve task failed: not found", result.output)
        self.assertIn(f"Missing BAID (options sample has no retrieved task): {BAID_A}", result.output)
        self.assertNotIn(f"Missing BAID (options sample has no retrieved task): {BAID_B}", result.output)
        api.tasks.get.assert_has_calls([mock.call(id="failed"), mock.call(id="second")])

    def test_malformed_manifests_fail_before_api_setup(self):
        cases = [
            ("", "baid or bioassay_id column"),
            ("file_name\nr1.fastq\n", "baid or bioassay_id column"),
            ("Bioassay_ID\tBAID\n", "exactly one"),
            ("Bioassay_ID\n", "Manifest contains no BAIDs"),
            ("Bioassay_ID\ninvalid\n", "invalid BAID 'invalid'"),
            (f"Bioassay_ID\nrerun_{BAID_A}\n", f"invalid BAID 'rerun_{BAID_A}'"),
            ("Bioassay_ID\tfile_name\n\tr1.fastq\n", "invalid BAID ''"),
            (f"Bioassay_ID\tfile_name\n{BAID_A}\n", "wrong number of columns"),
            (f"Bioassay_ID\tfile_name\n{BAID_A}\tr1.fastq\textra\n", "wrong number of columns"),
            (f'Bioassay_ID\tfile_name\n{BAID_A}\t"unterminated\n', "Unable to read input files"),
        ]
        for manifest, message in cases:
            with self.subTest(manifest=manifest):
                result, api, config, _ = self.invoke(manifest, {"first": task(BAID_A)})
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn(message, result.output)
                config.assert_not_called()
                api.tasks.get.assert_not_called()

    def test_empty_task_file_fails_before_api_setup(self):
        result, api, config, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {}, task_file="\n \n",
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("Task file contains no task IDs", result.output)
        config.assert_not_called()
        api.tasks.get.assert_not_called()

    def test_extra_task_for_same_options_row_fails(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A), "retry": task(BAID_A)},
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Task does not match an options row (or is an extra task for one)", result.output)
        self.assertIn("first", result.output)
        self.assertIn("retry", result.output)

    def test_partial_baid_is_not_a_match(self):
        result, _, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(f"{BAID_A}9_x{BAID_A}")},
        )
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Task name contains no BAID", result.output)

    def test_local_manifest_requires_demo(self):
        result, api, config, download = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A)}, local=True,
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("use --demo", result.output)
        config.assert_not_called()
        api.tasks.get.assert_not_called()
        download.assert_not_called()

    def test_demo_accepts_local_manifest_and_completed_tasks(self):
        result, _, _, download = self.invoke(
            f"\ufeffBAID,file_name\n{BAID_A},\"r1,paired.fastq\"\n",
            {"first": task(BAID_A, "COMPLETED")}, demo=True, local=True, options_local=True,
        )
        self.assertEqual(result.exit_code, 0, result.output)
        download.assert_not_called()

    def test_demo_also_accepts_github_manifests(self):
        result, _, _, download = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A, "RUNNING")}, demo=True,
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(download.call_count, 2)

    def test_local_options_require_demo(self):
        result, api, config, download = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A)}, options_local=True,
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("--options_file must be an HTTPS raw.githubusercontent.com URL", result.output)
        self.assertIn("use --demo", result.output)
        config.assert_not_called()
        api.tasks.get.assert_not_called()
        download.assert_called_once_with(MANIFEST_URL, headers={}, timeout=30)

    def test_demo_accepts_local_options_with_github_manifest(self):
        result, _, _, download = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A, "COMPLETED")},
            demo=True, options_local=True,
        )
        self.assertEqual(result.exit_code, 0, result.output)
        download.assert_called_once_with(MANIFEST_URL, headers={}, timeout=30)

    def test_options_download_failure_is_a_cli_error(self):
        result, api, config, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A)},
            options_error=requests.HTTPError("404"),
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn(f"Could not download options file {OPTIONS_URL}: 404", result.output)
        config.assert_not_called()
        api.tasks.get.assert_not_called()

    def test_manifest_and_options_readers_require_main_even_in_demo(self):
        url = "https://raw.githubusercontent.com/owner/repo/feature/input.tsv"
        with mock.patch.object(manifest_io.requests, "get") as download:
            for reader in (script.read_manifest_baids, script.read_options_rows):
                for demo in (False, True):
                    with self.subTest(reader=reader.__name__, demo=demo):
                        with self.assertRaisesRegex(script.click.ClickException, "GitHub main branch"):
                            reader(url, demo=demo)
            download.assert_not_called()

    def test_github_token_is_used_for_both_inputs(self):
        response = mock.Mock(content=b"example content")
        with (
            mock.patch.dict(manifest_io.os.environ, {"GITHUB_TOKEN": "test-token"}, clear=True),
            mock.patch.object(manifest_io.requests, "get", return_value=response) as download,
        ):
            script.load_input(MANIFEST_URL)
            script.load_input(OPTIONS_URL, option="--options_file")
        download.assert_has_calls([
            mock.call(MANIFEST_URL, headers={"Authorization": "Bearer test-token"}, timeout=30),
            mock.call(OPTIONS_URL, headers={"Authorization": "Bearer test-token"}, timeout=30),
        ])

    def test_github_download_failure_is_a_cli_error(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("tasks.txt").write_text("first\n")
            Path("options.tsv").write_text(f"output_basename\n{BAID_A}\n")
            with (
                mock.patch.object(manifest_io.requests, "get", side_effect=requests.HTTPError("404")),
                mock.patch.object(script.hf, "parse_config") as config,
            ):
                result = runner.invoke(script.task_validator, [
                    "--task_file", "tasks.txt", "--manifest", MANIFEST_URL,
                    "--options_file", "options.tsv",
                ])
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("Could not download manifest", result.output)
        self.assertEqual(result.output.splitlines()[-1], "Validation failed.")
        config.assert_not_called()

    def test_credentials_failure_is_a_runtime_error(self):
        result, api, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A)},
            credentials_error=KeyError("test"),
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("Unable to load API credentials for profile 'test'", result.output)
        api.tasks.get.assert_not_called()

    def test_unreadable_task_file_is_a_runtime_error(self):
        result, api, config, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n", {"first": task(BAID_A)},
            read_error=PermissionError("cannot read tasks.txt"),
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("Unable to read input files: cannot read tasks.txt", result.output)
        config.assert_not_called()
        api.tasks.get.assert_not_called()

    def test_runtime_error_takes_precedence_over_validation_discrepancies(self):
        result, api, _, _ = self.invoke(
            f"Bioassay_ID\n{BAID_A}\n{BAID_B}\n",
            {"failed": RuntimeError("fetch failed"), "second": task(BAID_B, "RUNNING")},
            options=f"output_basename\n{BAID_A}\n{BAID_B}\n",
        )
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("Unable to retrieve task failed: fetch failed", result.output)
        self.assertIn("Task is not DRAFT (status: RUNNING): second", result.output)
        self.assertEqual(api.tasks.get.call_count, 2)

    def test_usage_errors_have_runtime_exit_code_and_final_status(self):
        runner = CliRunner()
        for args in (["--unknown-option"], ["--manifest", MANIFEST_URL]):
            with self.subTest(args=args):
                result = runner.invoke(script.task_validator, args)
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertEqual(result.output.splitlines()[-1], "Validation failed.")

    def test_help_does_not_report_a_validation_result(self):
        result = CliRunner().invoke(script.task_validator, ["--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Usage:", result.output)
        self.assertNotIn("Validation passed.", result.output)
        self.assertNotIn("Validation failed.", result.output)


if __name__ == "__main__":
    unittest.main()
