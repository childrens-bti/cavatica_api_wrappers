import unittest
from helper_functions import parse_project


class TestCheckAndGetFiles(unittest.TestCase):
    def test_project_id(self):
        """Test when project is a project id (user/project)"""

        input_project = "test_user/test_project"
        expect_project = "test_user/test_project"

        # call the function
        out_project = parse_project(input_project)

        # test that the message is correct
        self.assertEqual(
            out_project,
            expect_project,
        )

    def test_project_url(self):
        """Test when project is a url ending in project id"""

        input_project = "https://cavatica.sbgenomics.com/u/test_user/test_project"
        expect_project = "test_user/test_project"

        # call the function
        out_project = parse_project(input_project)

        # test that the message is correct
        self.assertEqual(
            out_project,
            expect_project,
        )

    def test_project_app(self):
        """Test when project is a link to an app"""

        input_project = "https://cavatica.sbgenomics.com/u/sicklera/rood-epn-methylation/apps/unzip_and_sort_files/5"
        expect_project = "sicklera/rood-epn-methylation"

        # call the function
        out_project = parse_project(input_project)

        # test that the message is correct
        self.assertEqual(
            out_project,
            expect_project,
        )

    def test_project_task(self):
        """Test when project is a link to a task"""

        input_project = "https://cavatica.sbgenomics.com/u/sicklera/rood-epn-methylation/tasks/my-task-id/"
        expect_project = "sicklera/rood-epn-methylation"

        # call the function
        out_project = parse_project(input_project)

        # test that the message is correct
        self.assertEqual(
            out_project,
            expect_project,
        )

    def test_project_metrics(self):
        """Test when project is a link to a task instance metrics page"""

        input_project = "https://cavatica.sbgenomics.com/u/childrens-bti/intermediate-files-rmats-dev/tasks/my-task-id/instance-metrics/i-metrics"
        expect_project = "childrens-bti/intermediate-files-rmats-dev"

        # call the function
        out_project = parse_project(input_project)

        # test that the message is correct
        self.assertEqual(
            out_project,
            expect_project,
        )

    def test_project_part(self):
        """Test when project is part of a link"""

        input_project = "om/u/childrens-bti/intermediate-files-rmats-dev/"
        expect_project = "childrens-bti/intermediate-files-rmats-dev"

        # call the function
        out_project = parse_project(input_project)

        # test that the message is correct
        self.assertEqual(
            out_project,
            expect_project,
        )

    def test_project_part_different(self):
        """Test when project is (a different) part of a link.
        For now, fails if the url is missing the u/"""

        input_project = "sicklera/rood-epn-methylation/tasks"
        expect_project = "sicklera/rood-epn-methylation"

        # test that this raises an error
        with self.assertRaises(ValueError):
            parse_project(input_project)

    def test_project_malformed(self):
        """Test when project isn't correct"""

        input_project = "childrens-bti"
        expect_project = "childrens-bti/intermediate-files-rmats-dev"

        # test that this raises an error
        with self.assertRaises(ValueError):
            parse_project(input_project)


if __name__ == "__main__":
    unittest.main()
