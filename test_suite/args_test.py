import os

from base import TestBase

class ArgsTest(TestBase):
    snippet_dir = "args"

    def test_parameter_call(self):
        self.validate_snippet(self.get_snippet_path("call"))

    def test_assigned_parameter_call(self):
        self.validate_snippet(self.get_snippet_path("assigned_call"))

    def test_nested_parameter_call(self):
        self.validate_snippet(self.get_snippet_path("nested_call"))

    def test_imported_parameter_call(self):
        self.validate_snippet(self.get_snippet_path("imported_call"))

    def test_imported_assigned_parameter_call(self):
        self.validate_snippet(self.get_snippet_path("imported_assigned_call"))
