import unittest
from export_file_by_id import check_exportable


class MyStorage:
    """Test storage object"""

    def __init__(self, platform, volume):
        self.type = platform
        self.volume = volume


class MyFile:
    """Test file object"""

    def __init__(self, name, id, platform, volume):
        """create object, assign name and status"""
        self.name = name
        self.id = id
        self.storage = MyStorage(platform, volume)


class TestCheckAndGetFiles(unittest.TestCase):
    def test_no_issues(self):
        """Test when file is ok"""

        # create test file object
        file = MyFile("test_good_file", 108, "PLATFORM", None)

        # call the function
        res = check_exportable(file)

        self.assertTrue(res, "check exportable should return True")

    
    def test_duplicate_name(self):
        """Test when file is a duplicate basename (_#_file)"""

        # create test file object
        file = MyFile("_1_output_file.txt", 4815, "PLATFORM", None)

        # call the function
        res = check_exportable(file)

        self.assertFalse(res, "check exportable should return False")

    def test_multidigit_name(self):
        """Test when file is a duplicate basename (_##_file)"""

        # create test file object
        file = MyFile("_23_output_file.txt", 4815, "PLATFORM", None)

        # call the function
        res = check_exportable(file)

        self.assertFalse(res, "check exportable should return False")
    
    def test_doubleunder_name(self):
        """Test when has two underscores"""

        # create test file object
        file = MyFile("__23_output_file.txt", 4815, "PLATFORM", None)

        # call the function
        res = check_exportable(file)

        self.assertTrue(res, "check exportable should return True")
    
    def test_middle_name(self):
        """Test when a file has _#_ in the middile of the name"""

        # create test file object
        file = MyFile("chr_13.bed", 4815, "PLATFORM", None)

        # call the function
        res = check_exportable(file)

        self.assertTrue(res, "check exportable should return True")
    
    def test_already_exported(self):
        """Test when a file has already been exported"""

        # create test file object
        file = MyFile("chr_13.bed", 4815, "VOLUME", "assure")

                # call the function
        res = check_exportable(file)

        self.assertFalse(res, "check exportable should return False")

    def test_reference(self):
        """Test when trying to export a reference file"""

        # create test file object
        file = MyFile("GRCh38.primary_assembly.genome.fa", "6810e7eef8492c6e347f3037", "VOLUME", "kfdrc-harmonization/kf_reference")

                # call the function
        res = check_exportable(file)

        self.assertFalse(res, "check exportable should return False")

if __name__ == "__main__":
    unittest.main()
