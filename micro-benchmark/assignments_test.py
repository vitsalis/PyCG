
import os

from base import TestBase

class AssignmentsTest(TestBase):
    snippet_dir = "assignments"

    def test_tuple(self):
        self.validate_snippet(self.get_snippet_path("tuple"))

    def test_chained(self):
        self.validate_snippet(self.get_snippet_path("chained"))

    def test_recursive_tuple(self):
        self.validate_snippet(self.get_snippet_path("recursive_tuple"))

    def test_starred(self):
        self.validate_snippet(self.get_snippet_path("starred"))
