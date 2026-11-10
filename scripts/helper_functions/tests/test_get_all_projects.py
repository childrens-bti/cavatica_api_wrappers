import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

from sevenbridges.errors import SbgError
from sevenbridges.meta.collection import Collection

from helper_functions.helper_functions import get_all_projects


class TestGetAllProjects(unittest.TestCase):
    def page(self, projects, total=None):
        return Collection(resource=None, href="", total=len(projects) if total is None else total,
                          items=projects, links=[], api=None)

    def test_strict_listing_reads_each_page_once(self):
        api = Mock()
        projects = [SimpleNamespace(id=f"owner/project{i}") for i in range(101)]
        api.projects.query.side_effect = [
            self.page(projects[:100], 101), self.page(projects[100:], 101),
        ]
        self.assertEqual(get_all_projects(api, strict=True, owner="owner"), projects)
        self.assertEqual(api.projects.query.call_args_list, [
            call(limit=100, offset=0, owner="owner"),
            call(limit=100, offset=100, owner="owner"),
        ])

    def test_strict_listing_rejects_changed_page_totals_without_rescanning(self):
        api = Mock()
        projects = [SimpleNamespace(id=f"owner/project{i}") for i in range(102)]
        api.projects.query.side_effect = [
            self.page(projects[:100], 101), self.page(projects[100:], 102),
        ]
        with self.assertRaisesRegex(SbgError, "changed during pagination"):
            get_all_projects(api, strict=True)
        self.assertEqual(api.projects.query.call_count, 2)

    def test_strict_listing_rejects_duplicates_and_missing_entries(self):
        for incomplete in (False, True):
            with self.subTest(incomplete=incomplete):
                api = Mock()
                projects = [SimpleNamespace(id=f"owner/project{i}") for i in range(101)]
                bad_page = [] if incomplete else [projects[0]]
                api.projects.query.side_effect = [
                    self.page(projects[:100], 101), self.page(bad_page, 101),
                ]
                with self.assertRaisesRegex(SbgError, "incomplete or contained duplicate IDs"):
                    get_all_projects(api, strict=True)
                self.assertEqual(api.projects.query.call_count, 2)

    def test_strict_listing_propagates_api_errors(self):
        api = Mock()
        error = SbgError(message="Listing unavailable")
        api.projects.query.side_effect = error
        with self.assertRaises(SbgError) as raised:
            get_all_projects(api, strict=True)
        self.assertIs(raised.exception, error)
        api.projects.query.assert_called_once_with(limit=100, offset=0)

    def test_strict_listing_accepts_an_empty_page_without_rescanning(self):
        api = Mock()
        api.projects.query.return_value = self.page([])
        self.assertEqual(get_all_projects(api, strict=True), [])
        api.projects.query.assert_called_once_with(limit=100, offset=0)

    def test_default_listing_still_skips_unfetchable_projects(self):
        api = Mock()
        project = SimpleNamespace(id="owner/healthy")

        def query(limit=None, offset=None):
            if offset is None:
                return SimpleNamespace(total=2)
            if offset == 0:
                raise SbgError(message="Project serialization error")
            return [project] if offset == 1 else []

        api.projects.query.side_effect = query
        self.assertEqual(get_all_projects(api), [project])


if __name__ == "__main__":
    unittest.main()
