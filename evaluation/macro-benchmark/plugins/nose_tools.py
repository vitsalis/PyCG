"""A pytest plugin: the two functions of nose.tools that asciinema's tests use.

asciinema's tests import assert_equal and assert_raises from nose.tools.
nose 1.3.7, its last release (2015), cannot be imported on Python 3.12 and
later: importing nose.tools imports the package nose, whose importer imports
the module imp, which Python 3.12 removed. nose.tools defines its assert_*
functions as the methods of a unittest.TestCase. This plugin puts a module
nose.tools with those two methods in sys.modules before pytest collects the
tests, and changes nothing in the checkout. trace.py loads it from `plugins`
in projects.toml; for the tracer it is client code.
"""

import sys
import types
import unittest

_case = unittest.TestCase()  # the methods need an instance, not a test

tools = types.ModuleType("nose.tools")
tools.assert_equal = _case.assertEqual
tools.assert_raises = _case.assertRaises

nose = types.ModuleType("nose")
nose.__path__ = []  # a package, so that nose.tools is its submodule
nose.tools = tools

sys.modules["nose"] = nose
sys.modules["nose.tools"] = tools
