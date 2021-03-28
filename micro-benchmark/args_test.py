
import os

from base import TestBase

class ArgsTest(TestBase):
    snippet_dir = "args"

    def test_nested_call(self):
        self.validate_snippet(self.get_snippet_path("nested_call"))

    def test_param_call(self):
        self.validate_snippet(self.get_snippet_path("param_call"))

    def test_assigned_call(self):
        self.validate_snippet(self.get_snippet_path("assigned_call"))

    def test_imported_call(self):
        self.validate_snippet(self.get_snippet_path("imported_call"))

    def test_imported_assigned_call(self):
        self.validate_snippet(self.get_snippet_path("imported_assigned_call"))

    def test_call(self):
        self.validate_snippet(self.get_snippet_path("call"))
