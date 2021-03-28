
import os

from base import TestBase

class BuiltinsTest(TestBase):
    snippet_dir = "builtins"

    def test_types(self):
        self.validate_snippet(self.get_snippet_path("types"))

    def test_map(self):
        self.validate_snippet(self.get_snippet_path("map"))

    def test_functions(self):
        self.validate_snippet(self.get_snippet_path("functions"))
