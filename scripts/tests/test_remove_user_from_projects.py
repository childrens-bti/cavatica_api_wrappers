import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from click.testing import CliRunner

from remove_user_from_projects import remove_user


class TestRemoveUserFromProjects(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.api = Mock()
        self.config = patch("remove_user_from_projects.hf.parse_config", return_value=self.api)
        self.all_projects = patch("remove_user_from_projects.hf.get_all_projects")
        self.config_mock = self.config.start()
        self.projects_mock = self.all_projects.start()
        self.addCleanup(self.config.stop)
        self.addCleanup(self.all_projects.stop)

    def project(self, project_id, members=("target",)):
        project = Mock(id=project_id)
        project.get_members.return_value = [SimpleNamespace(username=user) for user in members]
        return project

    def test_requires_exactly_one_selector_before_api_access(self):
        for options in ([], ["--project", "owner/project", "--project_creator", "owner"]):
            with self.subTest(options=options):
                result = self.runner.invoke(remove_user, ["--user", "target", *options])
                self.assertEqual(result.exit_code, 2, result.output)
                self.config_mock.assert_not_called()

    def test_single_project_by_id_or_url(self):
        for project_arg in ("owner/project", "https://cavatica.sbgenomics.com/u/owner/project/"):
            with self.subTest(project_arg=project_arg):
                project = self.project("owner/project")
                self.api.projects.get.return_value = project
                result = self.runner.invoke(remove_user, ["--user", "target", "--project", project_arg])
                self.assertEqual(result.exit_code, 0, result.output)
                self.api.projects.get.assert_called_with(id="owner/project")
                self.projects_mock.assert_not_called()
                project.remove_member.assert_called_once_with(user="target")

    def test_absent_user_is_skipped(self):
        project = self.project("owner/project", members=("someone_else",))
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, ["--user", "target", "--project", "owner/project"])
        self.assertEqual(result.exit_code, 0, result.output)
        project.remove_member.assert_not_called()

    def test_creator_selection_and_reference_project_exclusion(self):
        projects = [self.project(project_id) for project_id in (
            "owner/project", "second/project", "other/project",
            "childrens-bti/childrens-bti-references",
        )]
        self.projects_mock.return_value = projects
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project_creator", "owner,second,childrens-bti",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.api.projects.get.assert_not_called()
        for project in projects[:2]:
            project.remove_member.assert_called_once_with(user="target")
        for project in projects[2:]:
            project.remove_member.assert_not_called()


if __name__ == "__main__":
    unittest.main()
