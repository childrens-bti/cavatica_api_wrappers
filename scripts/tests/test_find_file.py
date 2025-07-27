import unittest
import logging
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from find_file import find_file
import json


class TestFindFile(unittest.TestCase):
    @patch("find_file.hf.parse_config")
    @patch("find_file.hf.get_file_obj")
    #def test_find_file(self, mock_api, mock_file):
    def test_find_file(self, mock_file, mock_api):
        loglevel = logging.DEBUG
        logging.basicConfig(level=loglevel)
        log = logging.getLogger("LOG")
        #log.debug("")
        #log.debug(f"Function called with these args: {self}, {mock_file}, {mock_api}")

        # Configure the mock's return value
        #log.debug(mock_api.value)
        #log.debug(mock_file)
        #mock_api = ""
        mock_file.return_value.name = "BOB"
        mock_file.return_value.id = 1
        
        runner = CliRunner()
        result = runner.invoke(
            find_file,
            ["--file_name", "BOB", "--project", "sicklera/my_unittest_project"],
        )

        self.maxDiff = None
        #log.debug("OUTPUT: " + result.output)
        #log.debug("output done")
        self.assertEqual(
            result.output,
            "Searching for file BOB in project sicklera/my_unittest_project\n1\nBOB\n",
        )

if __name__ == "__main__":
    unittest.main()
