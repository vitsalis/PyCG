import os

from base import TestBase

class BuiltinsTest(TestBase):
    snippet_dir = "builtins"

    def test_map(self):
        self.validate_snippet(self.get_snippet_path("map"))
