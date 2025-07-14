import unittest
import io
import sys
from get_files_by_task import check_and_get_files


class MyClass:
    """Test class with status"""

    def __init__(self, name, status):
        """create object, assign name and status"""
        self.name = name
        self.status = status


class TestCheckAndGetFiles(unittest.TestCase):
    def test_draft_task(self):
        """Test when task status is draft"""

        # create test task object
        task = MyClass("test_draft_task", "DRAFT")

        # Create a string buffer to capture output
        captured_output = io.StringIO()
        # Redirect stdout to the buffer
        sys.stdout = captured_output
        # call the function
        out_files = check_and_get_files(task)
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # test that outputs are correct
        self.assertEqual(out_files, [])

        # test that the message is correct
        self.assertEqual(
            captured_output.getvalue(),
            "test_draft_task is a draft task and has not run yet, skipping\n",
        )

    def test_failed_task(self):
        """Test when input task status is failed"""

        # create test task object
        task = MyClass("test_failed_task", "FAILED")

        # Create a string buffer to capture output
        captured_output = io.StringIO()
        # Redirect stdout to the buffer
        sys.stdout = captured_output
        # call the function
        out_files = check_and_get_files(task)
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # test that outputs are correct
        self.assertEqual(out_files, [])

        # test that the message is correct
        self.assertEqual(
            captured_output.getvalue(), "test_failed_task has failed, skipping\n"
        )

    def test_unknown_task(self):
        """Test when input task status is an unknown status"""

        # create test task object
        task = MyClass("test_unknown_task", "DIFFERENT")

        # Create a string buffer to capture output
        captured_output = io.StringIO()
        # Redirect stdout to the buffer
        sys.stdout = captured_output
        # call the function
        out_files = check_and_get_files(task)
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # test that outputs are correct
        self.assertEqual(out_files, [])

        # test that the message is correct
        self.assertEqual(
            captured_output.getvalue(),
            "test_unknown_task is in an unknown state: DIFFERENT\nPlease check the task status and try again, skipping\n",
        )

    def test_completed_task(self):
        """Test when input task status is completed"""

        # create test task object
        task = MyClass("test_completed_task", "COMPLETED")
        task.outputs = {
            "output_vcf": "file1.vcf.gz",
            "intervar_classification": "intervar",
        }

        # Create a string buffer to capture output
        captured_output = io.StringIO()
        # Redirect stdout to the buffer
        sys.stdout = captured_output
        # call the function
        out_files = check_and_get_files(task)
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # test that outputs are correct
        self.assertEqual(out_files, ["file1.vcf.gz", "intervar"])

        # test that the message is correct
        self.assertEqual(captured_output.getvalue(), "")

    def test_list_output_task(self):
        """Test when output files are lists"""

        # create test task object
        task = MyClass("test_completed_task", "COMPLETED")
        task.outputs = {
            "output_vcfs": ["file1.vcf.gz", "file2.vcf.gz"],
            "intervar_classification": ["intervar"],
        }

        # Create a string buffer to capture output
        captured_output = io.StringIO()
        # Redirect stdout to the buffer
        sys.stdout = captured_output
        # call the function
        out_files = check_and_get_files(task)
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # test that outputs are correct
        self.assertEqual(out_files, ["file1.vcf.gz", "file2.vcf.gz", "intervar"])

        # test that the message is correct
        self.assertEqual(captured_output.getvalue(), "")

    def test_no_output_task(self):
        """Test when an output wasn't created"""

        # create test task object
        task = MyClass("test_completed_task", "COMPLETED")
        task.outputs = {
            "output_vcfs": ["file1.vcf.gz", "file2.vcf.gz"],
            "intervar_classification": None,
        }

        # Create a string buffer to capture output
        captured_output = io.StringIO()
        # Redirect stdout to the buffer
        sys.stdout = captured_output
        # call the function
        out_files = check_and_get_files(task)
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # test that outputs are correct
        self.assertEqual(out_files, ["file1.vcf.gz", "file2.vcf.gz"])

        # test that the message is correct
        self.assertEqual(captured_output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
