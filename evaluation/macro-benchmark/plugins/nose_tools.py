import sys
import types
import unittest

_test_case_instance = unittest.TestCase()

tools = types.ModuleType("nose.tools")
tools.assert_equal = _test_case_instance.assertEqual
tools.assert_raises = _test_case_instance.assertRaises

nose = types.ModuleType("nose")
nose.__path__ = []
nose.tools = tools

sys.modules["nose"] = nose
sys.modules["nose.tools"] = tools
