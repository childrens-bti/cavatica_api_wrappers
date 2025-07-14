import unittest
import logging
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from find_file import find_file
import json


class MyFile:
    """Test file object"""

    def __init__(self, name, id):
        """create object, assign name and status"""
        self.name = name
        self.id = id


class TestFindFile(unittest.TestCase):
    @patch("find_file.hf.parse_config")
    @patch("find_file.hf.get_file_obj")
    #def test_find_file(self, mock_api, mock_file):
    def test_find_file(self, mock_file, mock_api):
        loglevel = logging.DEBUG
        logging.basicConfig(level=loglevel)
        log = logging.getLogger("LOG")
        log.debug("")
        log.debug(f"Function called with these args: {self}, {mock_file}, {mock_api}")

        # Configure the mock's return value
        log.debug(mock_api)
        log.debug(mock_file)
        mock_api = ""
        #mock_file.return_value = json.dumps({"name": "BOB", "id": 1})
        """
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "BOB"
        #mock_file = None
        """
        mock_file = MyFile("BOB", 1)
        log.debug(mock_file)

        runner = CliRunner()
        result = runner.invoke(
            find_file,
            ["--file_name", "BOB", "--project", "sicklera/my_unittest_project"],
        )
        """
        log.debug(mock_file)
        log.debug(dir(mock_file))
        log.debug(mock_file.id)
        log.debug(mock_api)
        log.debug(dir(mock_api))
        log.debug(result.output)
        log.debug(dir(result))
        """
        log.debug(result.output)
        self.assertEqual(
            result.output,
            "Searching for file BOB in project sicklera/my_unittest_project\n1\nBOB\n",
        )

        self.assertEqual(result, "BOB")


if __name__ == "__main__":
    unittest.main()
