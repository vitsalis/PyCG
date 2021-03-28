
import os

from base import TestBase

class DirectCallsTest(TestBase):
    snippet_dir = "direct_calls"

    def test_with_parameters(self):
        self.validate_snippet(self.get_snippet_path("with_parameters"))

    def test_imported_return_call(self):
        self.validate_snippet(self.get_snippet_path("imported_return_call"))

    def test_return_call(self):
        self.validate_snippet(self.get_snippet_path("return_call"))

    def test_assigned_call(self):
        self.validate_snippet(self.get_snippet_path("assigned_call"))
