
import os

from base import TestBase

class ExceptionsTest(TestBase):
    snippet_dir = "exceptions"

    def test_raise(self):
        self.validate_snippet(self.get_snippet_path("raise"))

    def test_raise_attr(self):
        self.validate_snippet(self.get_snippet_path("raise_attr"))

    def test_raise_assigned(self):
        self.validate_snippet(self.get_snippet_path("raise_assigned"))
