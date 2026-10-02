import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import click

sys.path.insert(0, "scripts")

import generate_config_file


class TestInferOrganism(unittest.TestCase):
    def test_uses_human_organism_for_mixed_human_mouse_pdx_manifest(self):
        rows = [
            {
                "organism": "Homo sapiens",
                "pdx": "true",
                "experimental_strategy": "RNA-seq",
            },
            {
                "organism": "Mus musculus",
                "pdx": "true",
                "experimental_strategy": "RNA-seq",
            },
        ]
        self.assertEqual(
            generate_config_file.infer_organism(rows, pdx=True), "Homo sapiens"
        )

    def test_rejects_blank_organism_in_any_row(self):
        rows = [
            {"organism": "Homo sapiens"},
            {"organism": ""},
        ]

        with self.assertRaisesRegex(
            click.ClickException, r"blank organism value\(s\) in row\(s\): 3"
        ):
            generate_config_file.infer_organism(rows)

    def test_normalizes_organism_aliases(self):
        for value, expected in (("human", "Homo sapiens"), ("mouse", "Mus musculus")):
            with self.subTest(value=value):
                self.assertEqual(
                    generate_config_file.infer_organism([{"organism": value}]),
                    expected,
                )

    def test_rejects_unsupported_organism(self):
        with self.assertRaisesRegex(click.ClickException, "Unsupported organism 'canis'"):
            generate_config_file.infer_organism([{"organism": "canis"}])

    def test_rejects_mixed_organisms(self):
        rows = [{"organism": "human"}, {"organism": "mouse"}]

        with self.assertRaisesRegex(
            click.ClickException, "exactly one non-empty organism"
        ):
            generate_config_file.infer_organism(rows)


class TestExperimentalStrategyValidation(unittest.TestCase):
    def test_rejects_blank_strategy_in_any_row(self):
        rows = [
            {"experimental_strategy": "RNA-seq"},
            {"experimental_strategy": ""},
        ]

        with self.assertRaisesRegex(
            click.ClickException,
            r"blank experimental_strategy value\(s\) in row\(s\): 3",
        ):
            generate_config_file.validate_experimental_strategy(
                rows, "kfdrc_RNAseq_workflow"
            )

    def test_rejects_ribosome_profiling_rna_library_values(self):
        for rna_library in ("fragmented", "RPFs", " Fragmented ", "rpfs"):
            with self.subTest(rna_library=rna_library):
                rows = [
                    {
                        "experimental_strategy": "RNA-seq",
                        "RNA_library": rna_library,
                    }
                ]

                with self.assertRaisesRegex(click.ClickException, "fragmented library"):
                    generate_config_file.validate_experimental_strategy(
                        rows, "kfdrc_RNAseq_workflow"
                    )

    def test_accepts_non_ribosome_profiling_rna_library_value(self):
        strategy = generate_config_file.validate_experimental_strategy(
            [
                {
                    "experimental_strategy": "RNA-seq",
                    "RNA_library": "total RNA unstranded",
                }
            ],
            "kfdrc_RNAseq_workflow",
        )

        self.assertEqual(strategy, "rna-seq")

    def test_rejects_mixed_experimental_strategies(self):
        rows = [
            {"experimental_strategy": "RNA-seq"},
            {"experimental_strategy": "Ribo-seq"},
        ]

        with self.assertRaisesRegex(
            click.ClickException, "exactly one experimental_strategy"
        ):
            generate_config_file.validate_experimental_strategy(
                rows, "kfdrc_RNAseq_workflow"
            )

    def test_rejects_strategy_incompatible_with_rna_seq_workflow(self):
        with self.assertRaisesRegex(click.ClickException, "incompatible"):
            generate_config_file.validate_experimental_strategy(
                [{"experimental_strategy": "Ribo-seq"}],
                "kfdrc_RNAseq_workflow",
            )


class TestParseAppId(unittest.TestCase):
    def test_normalizes_valid_app_id(self):
        self.assertEqual(
            generate_config_file.parse_app_id("/childrens-bti/project/app/2/"),
            "childrens-bti/project/app/2",
        )

    def test_rejects_malformed_or_unrevisioned_app_id(self):
        for app_id in ("childrens-bti/project/app", "childrens-bti/project/app/x", "a/b/c/1/extra"):
            with self.subTest(app_id=app_id):
                with self.assertRaises(click.ClickException):
                    generate_config_file.parse_app_id(app_id)


class TestReadManifest(unittest.TestCase):
    def test_reads_csv_and_tsv_manifests(self):
        for suffix, delimiter in ((".csv", ","), (".tsv", "\t")):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / f"manifest{suffix}"
                path.write_text(
                    f" organism {delimiter} experimental_strategy \n"
                    f" human {delimiter} RNA-seq \n"
                )

                self.assertEqual(
                    generate_config_file.read_manifest(path.read_text(), path),
                    [{"organism": "human", "experimental_strategy": "RNA-seq"}],
                )

    def test_rejects_manifest_without_a_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.tsv"
            path.write_text("")

            with self.assertRaisesRegex(click.ClickException, "Manifest has no header"):
                generate_config_file.read_manifest(path.read_text(), path)

    def test_rejects_manifest_without_data_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "header_only.tsv"
            path.write_text("organism\texperimental_strategy\n")

            with self.assertRaisesRegex(click.ClickException, "contains no data rows"):
                generate_config_file.read_manifest(path.read_text(), path)


class TestLoadManifest(unittest.TestCase):
    def test_rejects_dot_segments_in_manifest_url_before_request(self):
        urls = (
            "https://raw.githubusercontent.com/owner/repository/main/../feature/manifest.tsv",
            "https://raw.githubusercontent.com/owner/repository/main/%2e%2e/feature/manifest.tsv",
            "https://raw.githubusercontent.com/owner/repository/main/%252e%252e/feature/manifest.tsv",
            "https://raw.githubusercontent.com/owner/repository/main%2f..%2ffeature/manifest.tsv",
        )

        with patch.object(generate_config_file.requests, "get") as get:
            for url in urls:
                with self.subTest(url=url):
                    with self.assertRaisesRegex(
                        click.ClickException, "dot path segments"
                    ):
                        generate_config_file.load_manifest(url)
            get.assert_not_called()


class TestBuildConfig(unittest.TestCase):
    app_id = "childrens-bti/project/kfdrc_RNAseq_workflow/0"

    def test_human_config_excludes_mouse_references(self):
        config = generate_config_file.build_config(
            [{"organism": "human", "experimental_strategy": "RNA-seq"}],
            self.app_id,
        )

        self.assertEqual(
            config,
            {
                "project": "childrens-bti/project",
                "app": self.app_id,
                "experimental_strategy": "rna-seq",
                "organism": "Homo sapiens",
            },
        )

    def test_mouse_config_includes_standard_references_and_disabled_tools(self):
        config = generate_config_file.build_config(
            [{"organism": "mouse", "experimental_strategy": "RNA-seq"}],
            self.app_id,
        )

        for key, value in generate_config_file.STANDARD_REFERENCES[
            "Mus musculus"
        ].items():
            self.assertEqual(config[key], value)
        self.assertFalse(config["run_t1k"])
        self.assertFalse(config["run_rmats"])
        self.assertFalse(config["run_fusions"])
