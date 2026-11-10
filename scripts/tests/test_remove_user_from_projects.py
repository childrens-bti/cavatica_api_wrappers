import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from click.testing import CliRunner
from sevenbridges.errors import Forbidden, SbgError
from sevenbridges.meta.collection import Collection

from remove_user_from_projects import remove_user
from helper_functions.helper_functions import get_all_projects


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
        project.get_members.return_value = self.member_page(members, len(members))
        return project

    def member_page(self, members, total):
        return Collection(
            resource=None, href="", total=total,
            items=[SimpleNamespace(username=user) for user in members],
            links=[], api=self.api,
        )

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

    def test_explicit_reference_project_is_rejected_before_api_access(self):
        for project_arg in (
            "childrens-bti/childrens-bti-references",
            "https://cavatica.sbgenomics.com/u/childrens-bti/childrens-bti-references/",
        ):
            with self.subTest(project_arg=project_arg):
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project", project_arg,
                ])
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn("protected reference project", result.output)
                self.config_mock.assert_not_called()
                self.api.projects.get.assert_not_called()
                self.projects_mock.assert_not_called()

    def test_single_project_permission_denial_returns_failure(self):
        for operation in ("get_members", "remove_member"):
            with self.subTest(operation=operation):
                project = self.project("owner/project")
                getattr(project, operation).side_effect = Forbidden(message="Denied")
                self.api.projects.get.return_value = project
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project", "owner/project",
                ])
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertIn("Could not verify or remove user target", result.output)
                self.assertIn("owner/project", result.output)
                self.assertNotIn("Finished removing user", result.output)
                if operation == "get_members":
                    project.remove_member.assert_not_called()

    def test_permission_denials_are_reported_after_remaining_projects(self):
        unreadable = self.project("owner/unreadable")
        unreadable.get_members.side_effect = Forbidden(message="Denied")
        unremovable = self.project("owner/unremovable")
        unremovable.remove_member.side_effect = Forbidden(message="Denied")
        removable = self.project("owner/removable")
        self.projects_mock.return_value = [unreadable, unremovable, removable]
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project_creator", "owner",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        unreadable.remove_member.assert_not_called()
        unremovable.remove_member.assert_called_once_with(user="target")
        removable.remove_member.assert_called_once_with(user="target")
        self.assertIn("in projects: owner/unreadable, owner/unremovable", result.output)
        self.assertNotIn("Finished removing user", result.output)

    def test_all_member_pages_are_checked_with_limit_100(self):
        for last_member in ("target", "someone_else"):
            with self.subTest(last_member=last_member):
                project = self.project("owner/project")
                project.get_members.side_effect = [
                    self.member_page([f"member{i}" for i in range(100)], 201),
                    self.member_page([f"member{i}" for i in range(100, 200)], 201),
                    self.member_page([last_member], 201),
                ]
                self.api.projects.get.return_value = project
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project", "owner/project",
                ])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(project.get_members.call_args_list, [
                    call(limit=100),
                    call(limit=100, offset=100),
                    call(limit=100, offset=200),
                ])
                if last_member == "target":
                    project.remove_member.assert_called_once_with(user="target")
                else:
                    project.remove_member.assert_not_called()

    def test_creator_selection_and_reference_project_exclusion(self):
        projects = [self.project(project_id) for project_id in (
            "owner/project", "second/project", "other/project",
            "childrens-bti/childrens-bti-references",
        )]
        self.projects_mock.return_value = projects
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project_creator", " owner, second , childrens-bti ",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.projects_mock.assert_called_once_with(self.api, strict=True)
        self.api.projects.get.assert_not_called()
        for project in projects[:2]:
            project.remove_member.assert_called_once_with(user="target")
        for project in projects[2:]:
            project.remove_member.assert_not_called()

    def test_listing_failure_stops_before_any_removals(self):
        project = self.project("owner/project")
        error = SbgError(message="Project serialization error")
        self.api.projects.query.side_effect = [
            SimpleNamespace(total=101),
            [project],
            error,
        ]
        with patch("remove_user_from_projects.hf.get_all_projects", wraps=get_all_projects):
            result = self.runner.invoke(remove_user, [
                "--user", "target", "--project_creator", "owner",
            ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIs(result.exception, error)
        project.get_members.assert_not_called()
        project.remove_member.assert_not_called()
        self.assertNotIn("Finished removing user", result.output)


if __name__ == "__main__":
    unittest.main()
