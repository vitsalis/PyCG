import io
import unittest

def helper():
    pass

class HelperTest(unittest.TestCase):
    def setUp(self):
        self.value = 1

    def test_helper(self):
        helper()

    def check_manually(self):
        pass

suite = unittest.defaultTestLoader.loadTestsFromTestCase(HelperTest)
unittest.TextTestRunner(stream=io.StringIO()).run(suite)
