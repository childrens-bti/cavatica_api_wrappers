import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

from sevenbridges.errors import SbgError

from helper_functions.helper_functions import get_all_projects


class TestGetAllProjects(unittest.TestCase):
    def test_strict_listing_returns_all_pages(self):
        api = Mock()
        first_page = [SimpleNamespace(id=f"owner/project{i}") for i in range(100)]
        last_project = SimpleNamespace(id="owner/last")
        api.projects.query.side_effect = [
            SimpleNamespace(total=101), first_page, [last_project],
        ]

        self.assertEqual(get_all_projects(api, strict=True), first_page + [last_project])
        self.assertEqual(api.projects.query.call_args_list, [
            call(limit=1), call(limit=100, offset=0), call(limit=100, offset=100),
        ])

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
