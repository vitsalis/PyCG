
import os

from base import TestBase

class FunctionsTest(TestBase):
    snippet_dir = "functions"

    def test_assigned_call(self):
        self.validate_snippet(self.get_snippet_path("assigned_call"))

    def test_imported_call(self):
        self.validate_snippet(self.get_snippet_path("imported_call"))

    def test_call(self):
        self.validate_snippet(self.get_snippet_path("call"))

    def test_assigned_call_lit_param(self):
        self.validate_snippet(self.get_snippet_path("assigned_call_lit_param"))
