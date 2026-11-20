import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import yaml
from click.testing import CliRunner

from create_project import ADMIN_USERS, REGULAR_USERS, create_project, parse_selections


class TestCreateProject(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.api = Mock()
        self.api.projects.create.return_value = Mock(id="owner/new-project")
        self.body = (
            "### Project_Name\n\nnew-project\n\n"
            "### Billing\n\nAWS-BTI-Core\n\n"
            "### Users\n\n- [x] bisong\n- [ ] JDAGGETT\n"
        )
        self.api_patch = patch("create_project.Api", return_value=self.api)
        self.api_patch.start()
        self.addCleanup(self.api_patch.stop)
        self.billing_patch = patch(
            "create_project.hf.get_all_billing",
            return_value=[SimpleNamespace(name="AWS-BTI-Core", id="billing-id")],
        )
        self.billing_patch.start()
        self.addCleanup(self.billing_patch.stop)

    def run_project(self, body, run=True):
        return self.runner.invoke(
            create_project,
            ["--token", "test-token"] + (["--run"] if run else []),
            env={"BODY": body, "URL": "https://github.com/example/issues/1"},
        )

    def test_creates_project_with_selected_tags_and_expected_members(self):
        body = self.body + (
            "\n### PI\n\n- [x] Haydar\n- [ ] Rood\n\n"
            "### Project\n\n- [x] CNH DMG\n- [X] SUPERNOVA\n\n"
            "### Experimental_Strategy\n\n- [x] RNA-Seq\n- [ ] WGS\n"
        )
        result = self.run_project(body)
        self.assertEqual(result.exit_code, 0, result.output)
        self.api.projects.create.assert_called_once_with(
            name="new-project",
            billing_group="billing-id",
            description="https://github.com/example/issues/1",
            tags=["Haydar", "CNH DMG", "SUPERNOVA", "RNA-Seq"],
            settings={"use_memoization": True, "allow_network_access": True},
        )
        member_calls = self.api.projects.create.return_value.add_member.call_args_list
        self.assertEqual(
            [entry.kwargs["user"] for entry in member_calls],
            ADMIN_USERS + ["bisong"] + REGULAR_USERS,
        )
        self.assertTrue(all(
            entry.kwargs["permissions"]["admin"]
            for entry in member_calls[:len(ADMIN_USERS)]
        ))
        self.assertTrue(all(
            entry.kwargs["permissions"]["copy"]
            for entry in member_calls[len(ADMIN_USERS):]
        ))

    def test_legacy_and_unselected_forms_create_without_tags(self):
        for extra in (
            "",
            "\n### PI\n\n_No response_\n\n### Project\n\n- [ ] SUPERNOVA\n\n"
            "### Experimental_Strategy\n\n_No response_\n\n### dev\n\n- [ ] dev\n",
        ):
            with self.subTest(extra=extra):
                self.api.projects.create.reset_mock()
                result = self.run_project(self.body + extra)
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(self.api.projects.create.call_args.kwargs["tags"], [])

    def test_text_values_and_crlf_preserve_spaces_and_deduplicate_tags(self):
        body = self.body + (
            "\n### PI\n\n Haydar, Haydar \n\n"
            "### Project\n\nCNH DMG, SUPERNOVA\n\n"
            "### Experimental_Strategy\n\n RNA-Seq, CNH DMG, \n"
        )
        result = self.run_project(body.replace("\n", "\r\n"))
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            self.api.projects.create.call_args.kwargs["tags"],
            ["Haydar", "CNH DMG", "SUPERNOVA", "RNA-Seq"],
        )

    def test_dry_run_displays_tags_without_creating_project(self):
        result = self.run_project(self.body + "\n### PI\n\n- [x] Haydar\n", run=False)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("tags=['Haydar']", result.output)
        self.api.projects.create.assert_not_called()

    def test_unknown_fields_fail_before_creating_project(self):
        result = self.run_project(self.body + "\n### Unexpected\n\nvalue\n")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIsInstance(result.exception, ValueError)
        self.api.projects.create.assert_not_called()

    def test_template_selections_reach_project_creation(self):
        template = yaml.safe_load(
            (Path(__file__).resolve().parents[2] / ".github/ISSUE_TEMPLATE/project_creation.yml").read_text()
        )
        body = ""
        expected_tags = []
        for field in template["body"]:
            attributes = field["attributes"]
            label = attributes["label"]
            if field["type"] == "input":
                value = {"Project_Name": "new-project", "Billing": "AWS-BTI-Core"}[label]
            else:
                selected = "PBTA" if label == "Project" else attributes["options"][0]["label"]
                value = "\n".join(
                    f"- [{'x' if option['label'] == selected else ' '}] {option['label']}"
                    for option in attributes["options"]
                )
                if label != "Users":
                    expected_tags.append(selected)
                    self.assertTrue(all(
                        not option.get("required", False)
                        for option in attributes["options"]
                    ))
            body += f"### {label}\n\n{value}\n\n"
        result = self.run_project(body)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(expected_tags, ["Bollard", "PBTA", "10x Flex GEX", "dev"])
        self.assertEqual(self.api.projects.create.call_args.kwargs["tags"], expected_tags)


class TestParseSelections(unittest.TestCase):
    def test_checkbox_labels_preserve_punctuation_and_ignore_unchecked_options(self):
        self.assertEqual(
            parse_selections("- [ ] WGS\n- [x] RNA-Seq\n- [X] Study, phase 2\n"),
            ["RNA-Seq", "Study, phase 2"],
        )

    def test_empty_selections(self):
        for value in ("", " \n", "_No response_", "- [ ] WGS\n", " , , "):
            with self.subTest(value=value):
                self.assertEqual(parse_selections(value), [])


if __name__ == "__main__":
    unittest.main()
