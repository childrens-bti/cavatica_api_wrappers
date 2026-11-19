import unittest
from unittest.mock import Mock, call, patch

from click.testing import CliRunner

from update_project_tags import update_project_tags


class TestUpdateProjectTags(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.api = Mock()

    def run_tags(self, rows):
        with self.runner.isolated_filesystem():
            with open("tags.tsv", "w") as tag_file:
                tag_file.write("project\ttag\n" + rows)
            with patch("update_project_tags.hf.parse_config", return_value=self.api):
                return self.runner.invoke(
                    update_project_tags, ["--tag_file", "tags.tsv", "--verbose"]
                )

    def project(self, project_id, tags):
        project = Mock(id=project_id, tags=tags)
        self.api.projects.get.return_value = project
        return project

    def test_preserves_existing_tags_and_adds_only_unique_new_tags(self):
        project = self.project("owner/project", ["existing"])
        result = self.run_tags("owner/project\t existing, new ,new,RNA sequencing\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(project.tags, ["existing", "new", "RNA sequencing"])
        project.save.assert_called_once_with()
        self.assertIn("Added tags to owner/project: new, RNA sequencing", result.output)
        self.assertIn("Added tags to 1 projects", result.output)

    def test_existing_and_empty_tags_do_not_save_or_count(self):
        project = self.project("owner/project", ["existing"])
        result = self.run_tags(
            "owner/project\texisting, existing\nowner/empty\t , \n"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        project.save.assert_not_called()
        self.api.projects.get.assert_called_once_with("owner/project")
        self.assertIn("Added tags to 0 projects", result.output)
        self.assertNotIn("Added tags to owner/project:", result.output)

    def test_repeated_projects_add_new_tags_but_are_counted_once(self):
        project = self.project("owner/project", None)
        saved_tags = []
        project.save.side_effect = lambda: saved_tags.append(list(project.tags))
        rows = (
            "owner/project\tfirst,first\n"
            "https://cavatica.sbgenomics.com/u/owner/project/\tfirst\n"
            "owner/project\tfirst,second\n"
        )
        result = self.run_tags(rows)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(saved_tags, [["first"], ["first", "second"]])
        self.assertEqual(self.api.projects.get.call_args_list, [
            call("owner/project"), call("owner/project"), call("owner/project"),
        ])
        self.assertIn("Added tags to 1 projects", result.output)

        project.save.reset_mock()
        result = self.run_tags(rows)
        self.assertEqual(result.exit_code, 0, result.output)
        project.save.assert_not_called()
        self.assertIn("Added tags to 0 projects", result.output)

    def test_distinct_updated_projects_are_counted(self):
        first = Mock(id="owner/first", tags=[])
        second = Mock(id="owner/second", tags=[])
        self.api.projects.get.side_effect = [first, second]
        result = self.run_tags("owner/first\tnew\nowner/second\tnew\n")
        self.assertEqual(result.exit_code, 0, result.output)
        first.save.assert_called_once_with()
        second.save.assert_called_once_with()
        self.assertIn("Added tags to 2 projects", result.output)


if __name__ == "__main__":
    unittest.main()
