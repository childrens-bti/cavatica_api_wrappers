import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from click.testing import CliRunner
from requests.exceptions import ConnectionError
from sevenbridges.errors import Forbidden, NotFound, SbgError
from sevenbridges.meta.collection import Collection

from remove_user_from_projects import remove_user
from helper_functions.helper_functions import get_all_projects


class TestRemoveUserFromProjects(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.api = Mock()
        self.api.users.me.return_value = SimpleNamespace(username="operator")
        self.config = patch("remove_user_from_projects.hf.parse_config", return_value=self.api)
        self.all_projects = patch("remove_user_from_projects.hf.get_all_projects")
        self.config_mock = self.config.start()
        self.projects_mock = self.all_projects.start()
        self.addCleanup(self.config.stop)
        self.addCleanup(self.all_projects.stop)
        self.sleep = patch("remove_user_from_projects.time.sleep")
        self.sleep_mock = self.sleep.start()
        self.addCleanup(self.sleep.stop)

        def scoped_projects(api, strict=False, owner=None):
            return [
                project for project in self.projects_mock.return_value
                if owner is None or project.id.split("/")[0].casefold() == owner
            ]

        self.projects_mock.side_effect = scoped_projects

    def project(self, project_id, members=("target",)):
        project = Mock(id=project_id)
        project.get_members.return_value = self.member_page(members, len(members))

        current_members = list(members)

        def remove_member(user):
            current_members[:] = [name for name in current_members if name != user]
            remaining = current_members
            project.get_members.side_effect = None
            project.get_members.return_value = self.member_page(remaining, len(remaining))

        project.remove_member.side_effect = remove_member
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

    def test_empty_username_is_rejected_before_api_access(self):
        for user in ("", " ", "\t\n"):
            with self.subTest(user=user):
                result = self.runner.invoke(remove_user, [
                    "--user", user, "--project", "owner/project",
                ])
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn("Username must not be empty", result.output)
                self.config_mock.assert_not_called()

    def test_username_is_trimmed_before_removal(self):
        project = self.project("owner/project")
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", " target ", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        project.remove_member.assert_called_once_with(user="target")
        self.assertIn("Confirmed absent (1): owner/project", result.output)

    def test_username_case_matches_the_member_list_for_removal_and_verification(self):
        for removed in (True, False):
            with self.subTest(removed=removed):
                project = self.project("owner/project")
                if not removed:
                    project.remove_member.side_effect = None
                self.api.projects.get.return_value = project
                result = self.runner.invoke(remove_user, [
                    "--user", "TARGET", "--project", "owner/project",
                ])
                self.assertEqual(project.remove_member.call_args_list, [call(user="target")] * (1 if removed else 5))
                self.assertEqual(result.exit_code, 0 if removed else 1, result.output)
                status = "Confirmed absent" if removed else "Still has access"
                self.assertIn(f"{status} (1): owner/project", result.output)

    def test_self_removal_is_rejected_before_project_access(self):
        self.api.users.me.return_value = SimpleNamespace(username="target")
        for selector in (["--project", "owner/project"], ["--project_creator", "owner"]):
            for user in ("target", " target ", "TARGET"):
                with self.subTest(selector=selector, user=user):
                    result = self.runner.invoke(remove_user, ["--user", user, *selector])
                    self.assertEqual(result.exit_code, 1, result.output)
                    self.assertIn("Cannot remove the authenticated user target", result.output)
                    self.api.projects.get.assert_not_called()
                    self.projects_mock.assert_not_called()

    def test_identity_lookup_failure_stops_before_project_access(self):
        error = SbgError(message="Could not fetch current user")
        self.api.users.me.side_effect = error
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIs(result.exception, error)
        self.api.projects.get.assert_not_called()
        self.projects_mock.assert_not_called()

    def test_empty_creator_entries_are_rejected_before_api_access(self):
        for creators in ("", " ", ",", "owner,", ",owner", "owner, ,second"):
            with self.subTest(creators=creators):
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project_creator", creators,
                ])
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn("without empty entries", result.output)
                self.config_mock.assert_not_called()
                self.projects_mock.assert_not_called()

    def test_unmatched_owners_return_failure_with_eligible_count(self):
        for creators, count in (("typo", 0), ("owner,typo", 1)):
            with self.subTest(creators=creators):
                project = self.project("owner/project")
                unrelated = self.project("other/project")
                self.projects_mock.return_value = [project, unrelated]
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project_creator", creators,
                ])
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertIn("No projects matched owners: typo", result.output)
                self.assertIn(f"{count} eligible project(s)", result.output)
                self.assertNotIn("Finished removing user", result.output)
                self.assertEqual(project.remove_member.call_count, count)
                unrelated.get_members.assert_not_called()

    def test_malformed_project_is_rejected_before_api_access(self):
        for project_arg in (
            "", " ", "owner", "/project", "owner/", "owner/ ",
            "https://cavatica.sbgenomics.com/u/",
            "https://cavatica.sbgenomics.com/u/owner/",
        ):
            with self.subTest(project_arg=project_arg):
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project", project_arg,
                ])
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn("Invalid value for --project", result.output)
                self.assertIn("owner/project", result.output)
                self.config_mock.assert_not_called()

    def test_unmatched_owners_and_permission_denials_are_both_reported(self):
        project = self.project("owner/project")
        project.get_members.side_effect = Forbidden(message="Denied")
        self.projects_mock.return_value = [project]
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project_creator", "owner,typo",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("No projects matched owners: typo", result.output)
        self.assertIn("Could not verify membership for user target", result.output)

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
        self.assertIn("Confirmed absent (1): owner/project", result.output)
        self.assertNotIn("Removed (", result.output)

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
                message = "Could not verify membership" if operation == "get_members" else "still has access"
                self.assertIn(message, result.output)
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
        self.assertEqual(unreadable.get_members.call_count, 1)
        self.assertEqual(unremovable.get_members.call_count, 2)
        self.sleep_mock.assert_not_called()
        removable.remove_member.assert_called_once_with(user="target")
        self.assertIn("Confirmed absent (1): owner/removable", result.output)
        self.assertIn("Could not verify (1): owner/unreadable", result.output)
        self.assertIn("Still has access (1): owner/unremovable", result.output)
        self.assertNotIn("Not processed (", result.output)
        self.assertNotIn("Finished removing user", result.output)

    def test_removal_failure_retries_unresolved_projects_after_verification(self):
        for operation in ("get_members", "remove_member"):
            with self.subTest(operation=operation):
                removed = self.project("owner/removed")
                absent = self.project("owner/absent", members=("someone_else",))
                failed = self.project("owner/failed")
                unprocessed = self.project("owner/unprocessed")
                error = SbgError(message="Internal server error")
                getattr(failed, operation).side_effect = error
                self.projects_mock.return_value = [removed, absent, failed, unprocessed]
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project_creator", "owner",
                ])
                self.assertEqual(result.exit_code, 1, result.output)
                removed.remove_member.assert_called_once_with(user="target")
                absent.remove_member.assert_not_called()
                self.assertEqual(unprocessed.get_members.call_args_list, [call(limit=100)] * 2)
                unprocessed.remove_member.assert_called_once_with(user="target")
                self.assertIn("Confirmed absent (3): owner/removed, owner/absent, owner/unprocessed", result.output)
                if operation == "get_members":
                    self.assertIn("Could not verify (1): owner/failed", result.output)
                else:
                    self.assertIn("Still has access (1): owner/failed", result.output)
                self.assertNotIn("Finished removing user", result.output)
                if operation == "get_members":
                    failed.remove_member.assert_not_called()

    def test_final_check_confirms_removal_after_lost_delete_response(self):
        project = self.project("owner/project")
        error = ConnectionError("DELETE response lost")

        def remove_then_disconnect(user):
            project.get_members.return_value = self.member_page([], 0)
            raise error

        project.remove_member.side_effect = remove_then_disconnect
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(len(project.get_members.return_value), 0)
        project.remove_member.assert_called_once_with(user="target")
        self.assertEqual(project.get_members.call_args_list, [call(limit=100), call(limit=100)])
        self.assertIn("Confirmed absent (1): owner/project", result.output)
        self.assertNotIn("Failed to verify or remove (", result.output)

    def test_successful_delete_response_is_not_enough_if_user_is_still_present(self):
        project = self.project("owner/project")
        project.remove_member.side_effect = None  # Acknowledged, but no state change.
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Still has access (1): owner/project", result.output)
        self.assertEqual(project.remove_member.call_count, 5)
        self.assertNotIn("Attempt 6/5", result.output)
        self.assertNotIn("Confirmed absent (", result.output)
        self.assertNotIn("Finished removing user", result.output)

    def test_final_check_failure_does_not_report_confirmed_removal(self):
        project = self.project("owner/project")
        project.remove_member.side_effect = None
        project.get_members.side_effect = [
            self.member_page(["target"], 1),
            *[SbgError(message="Verification unavailable")] * 9,
        ]
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        project.remove_member.assert_called_once_with(user="target")
        self.assertIn("Could not verify (1): owner/project", result.output)
        self.assertNotIn("Confirmed absent (", result.output)

    def test_final_check_reads_all_pages_even_if_user_was_initially_absent(self):
        project = self.project("owner/project", members=())
        project.get_members.side_effect = [
            self.member_page([], 0),
            self.member_page([f"member{i}" for i in range(100)], 101),
            self.member_page(["target"], 101),
            self.member_page(["target"], 1),
        ]
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        project.remove_member.assert_called_once_with(user="target")
        self.assertEqual(project.get_members.call_args_list, [
            call(limit=100), call(limit=100), call(limit=100, offset=100),
            call(limit=100),
        ])
        self.assertIn("Confirmed absent (1): owner/project", result.output)

    def test_verification_starts_after_all_removal_attempts(self):
        first = self.project("owner/first")
        second = self.project("owner/second")
        calls = Mock()
        calls.attach_mock(first.get_members, "read_first")
        calls.attach_mock(first.remove_member, "remove_first")
        calls.attach_mock(second.get_members, "read_second")
        calls.attach_mock(second.remove_member, "remove_second")
        self.projects_mock.return_value = [first, second]
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project_creator", "owner",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(calls.mock_calls, [
            call.read_first(limit=100), call.remove_first(user="target"),
            call.read_second(limit=100), call.remove_second(user="target"),
            call.read_first(limit=100), call.read_second(limit=100),
        ])

    def test_retry_only_unresolved_projects_and_stop_when_all_15_are_absent(self):
        projects = [self.project(f"owner/project{i:02d}") for i in range(1, 16)]
        for project in projects[13:]:
            remove = project.remove_member.side_effect

            def remove_on_second_attempt(user, project=project, remove=remove):
                if project.remove_member.call_count == 2:
                    remove(user)

            project.remove_member.side_effect = remove_on_second_attempt
        self.projects_mock.return_value = projects
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project_creator", "owner",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        for project in projects[:13]:
            project.remove_member.assert_called_once_with(user="target")
            self.assertEqual(project.get_members.call_count, 2)
        for project in projects[13:]:
            self.assertEqual(project.remove_member.call_count, 2)
        self.assertIn("Attempt 2/5: retrying 2 unresolved project(s)", result.output)
        self.assertIn("Confirmed absent (15):", result.output)
        self.assertNotIn("Attempt 3/5", result.output)

    def test_fifth_attempt_can_succeed_after_removal_errors(self):
        project = self.project("owner/project")
        remove = project.remove_member.side_effect

        def remove_on_fifth_attempt(user):
            if project.remove_member.call_count < 5:
                raise ConnectionError("Temporary removal failure")
            remove(user)

        project.remove_member.side_effect = remove_on_fifth_attempt
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(project.remove_member.call_count, 5)
        self.assertIn("Confirmed absent (1): owner/project", result.output)
        self.assertNotIn("Attempt 6/5", result.output)

    def test_failed_verification_is_rechecked_without_repeating_applied_removal(self):
        project = self.project("owner/project")
        remove = project.remove_member.side_effect

        def remove_then_fail_verification(user):
            remove(user)
            project.get_members.side_effect = [
                SbgError(message="Temporary verification failure"),
                self.member_page([], 0), self.member_page([], 0),
            ]

        project.remove_member.side_effect = remove_then_fail_verification
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        project.remove_member.assert_called_once_with(user="target")
        self.assertEqual(project.get_members.call_count, 3)
        self.assertIn("Confirmed absent (1): owner/project", result.output)
        self.assertNotIn("Attempt 3/5", result.output)

    def test_interruption_during_retry_stops_without_further_requests(self):
        project = self.project("owner/project")
        project.remove_member.side_effect = [None, KeyboardInterrupt()]
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertEqual(project.remove_member.call_count, 2)
        self.assertEqual(project.get_members.call_count, 2)
        self.assertIn("Outcome unconfirmed (1): owner/project", result.output)
        self.assertNotIn("Attempt 3/5", result.output)

    def test_interruption_does_not_claim_current_project_was_unprocessed(self):
        removed = self.project("owner/removed")
        interrupted = self.project("owner/interrupted")
        interrupted.remove_member.side_effect = KeyboardInterrupt()
        unprocessed = self.project("owner/unprocessed")
        self.projects_mock.return_value = [removed, interrupted, unprocessed]
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project_creator", "owner",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Removed (1): owner/removed", result.output)
        self.assertIn("Outcome unconfirmed (1): owner/interrupted", result.output)
        self.assertIn("Not processed (1): owner/unprocessed", result.output)
        unprocessed.get_members.assert_not_called()
        self.assertNotIn("Finished removing user", result.output)

    def test_interrupted_membership_check_is_failed_verification(self):
        project = self.project("owner/project")
        project.get_members.side_effect = KeyboardInterrupt()
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        project.remove_member.assert_not_called()
        self.assertIn("Failed to verify or remove (1): owner/project", result.output)
        self.assertNotIn("Outcome unconfirmed (", result.output)

    def test_all_member_pages_are_checked_with_limit_100(self):
        for last_member in ("target", "someone_else"):
            with self.subTest(last_member=last_member):
                project = self.project("owner/project")
                project.get_members.side_effect = [
                    self.member_page([f"member{i}" for i in range(100)], 201),
                    self.member_page([f"member{i}" for i in range(100, 200)], 201),
                    self.member_page([last_member], 201),
                    self.member_page([last_member], 1),
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
                    call(limit=100),
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
        self.assertEqual(self.projects_mock.call_args_list, [
            call(self.api, strict=True, owner="childrens-bti"),
            call(self.api, strict=True, owner="owner"),
            call(self.api, strict=True, owner="second"),
        ])
        self.api.projects.get.assert_not_called()
        for project in projects[:2]:
            project.remove_member.assert_called_once_with(user="target")
        for project in projects[2:]:
            project.remove_member.assert_not_called()
        self.assertIn("2 eligible project(s)", result.output)
        self.assertIn("Confirmed absent (2): owner/project, second/project", result.output)
        self.assertIn(
            "Protected/skipped (1): childrens-bti/childrens-bti-references",
            result.output,
        )
        self.assertNotIn("no projects matched owner childrens-bti", result.output)
        projects[-1].get_members.assert_not_called()

    def test_protected_project_is_reported_only_when_its_owner_is_selected(self):
        reference = self.project("childrens-bti/childrens-bti-references")
        regular = self.project("owner/project")
        regular.created_by = "childrens-bti"
        self.projects_mock.return_value = [reference, regular]
        for owner, eligible_count in (("childrens-bti", 0), ("owner", 1)):
            with self.subTest(owner=owner):
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project_creator", owner,
                ])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn(f"{eligible_count} eligible project(s)", result.output)
                self.assertEqual("Protected/skipped" in result.output, owner == "childrens-bti")
                self.assertNotIn("no projects matched", result.output)
                reference.get_members.assert_not_called()
                reference.remove_member.assert_not_called()
                self.assertEqual(regular.remove_member.call_count, eligible_count)

    def test_listing_failure_stops_before_any_removals(self):
        project = self.project("owner/project")
        error = SbgError(message="Project serialization error")
        self.api.projects.query.side_effect = [
            Collection(resource=None, href="", total=101,
                       items=[project] * 100, links=[], api=self.api),
            error,
        ]
        with patch("remove_user_from_projects.hf.get_all_projects", wraps=get_all_projects):
            result = self.runner.invoke(remove_user, [
                "--user", "target", "--project_creator", "owner",
            ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Could not load selected projects", result.output)
        self.assertIn("Project serialization error", result.output)
        project.get_members.assert_not_called()
        project.remove_member.assert_not_called()
        self.assertNotIn("Finished removing user", result.output)

    def test_explicit_lookup_failures_are_cli_errors(self):
        for error_type in (NotFound, Forbidden):
            with self.subTest(error_type=error_type):
                self.api.projects.get.side_effect = error_type(message="Unavailable")
                result = self.runner.invoke(remove_user, [
                    "--user", "target", "--project", "owner/missing",
                ])
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertIn("Error: Could not load selected projects", result.output)
                self.assertIn("Unavailable", result.output)
                self.assertNotIn("Finished removing user", result.output)

    def test_owner_names_are_normalized_and_deduplicated(self):
        project = self.project("childrens-bti/project")
        self.projects_mock.return_value = [project]
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project_creator", " Childrens-BTI,childrens-bti ",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.projects_mock.assert_called_once_with(self.api, strict=True, owner="childrens-bti")
        project.remove_member.assert_called_once_with(user="target")

    def test_owner_listing_never_queries_unselected_broken_projects(self):
        project = self.project("owner/project")

        def query(owner=None, limit=None, offset=None):
            if owner != "owner":
                raise SbgError(message="Unselected project cannot be serialized")
            return Collection(resource=None, href="", total=1,
                              items=[project], links=[], api=self.api)

        self.api.projects.query.side_effect = query
        with patch("remove_user_from_projects.hf.get_all_projects", wraps=get_all_projects):
            result = self.runner.invoke(remove_user, [
                "--user", "target", "--project_creator", "owner",
            ])
        self.assertEqual(result.exit_code, 0, result.output)
        project.remove_member.assert_called_once_with(user="target")
        self.assertTrue(all(c.kwargs["owner"] == "owner" for c in self.api.projects.query.call_args_list))

    def test_all_case_variants_are_removed_in_one_attempt(self):
        project = self.project("owner/project", members=("Target", "target", "TARGET", "other"))
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(project.remove_member.call_args_list, [
            call(user="Target"), call(user="target"), call(user="TARGET"),
        ])
        self.sleep_mock.assert_not_called()

    def test_retries_back_off_and_reuse_verified_membership(self):
        project = self.project("owner/project")
        project.remove_member.side_effect = None
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertEqual(self.sleep_mock.call_args_list, [call(5), call(10), call(20), call(40)])
        self.assertEqual(project.remove_member.call_count, 5)
        self.assertEqual(project.get_members.call_count, 6)

    def test_interruption_during_backoff_stops_before_retry(self):
        project = self.project("owner/project")
        project.remove_member.side_effect = None
        self.api.projects.get.return_value = project
        self.sleep_mock.side_effect = KeyboardInterrupt()
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        project.remove_member.assert_called_once_with(user="target")
        self.assertEqual(project.get_members.call_count, 2)
        self.assertIn("Still has access (1): owner/project", result.output)

    def test_membership_page_changes_are_not_confirmed_absent(self):
        project = self.project("owner/project")
        first = self.member_page([f"user{i}" for i in range(100)], 101)
        second = self.member_page([], 100)
        project.get_members.side_effect = [first, second] * 10
        self.api.projects.get.return_value = project
        result = self.runner.invoke(remove_user, [
            "--user", "target", "--project", "owner/project",
        ])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Could not verify (1): owner/project", result.output)
        self.assertNotIn("Confirmed absent", result.output)
        project.remove_member.assert_not_called()


if __name__ == "__main__":
    unittest.main()
