
import os

from base import TestBase

class ListsTest(TestBase):
    snippet_dir = "lists"

    def test_comprehension_val(self):
        self.validate_snippet(self.get_snippet_path("comprehension_val"))

    def test_slice(self):
        self.validate_snippet(self.get_snippet_path("slice"))

    def test_simple(self):
        self.validate_snippet(self.get_snippet_path("simple"))

    def test_comprehension_if(self):
        self.validate_snippet(self.get_snippet_path("comprehension_if"))

    def test_nested_comprehension(self):
        self.validate_snippet(self.get_snippet_path("nested_comprehension"))

    def test_param_index(self):
        self.validate_snippet(self.get_snippet_path("param_index"))

    def test_nested(self):
        self.validate_snippet(self.get_snippet_path("nested"))

    def test_ext_index(self):
        self.validate_snippet(self.get_snippet_path("ext_index"))
