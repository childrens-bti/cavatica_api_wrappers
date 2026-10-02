import sys
import unittest

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
        for rna_library in ("fragmented", "RPFs"):
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
