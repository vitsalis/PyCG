
import os

from base import TestBase

class ReturnsTest(TestBase):
    snippet_dir = "returns"

    def test_return_complex(self):
        self.validate_snippet(self.get_snippet_path("return_complex"))

    def test_imported_call(self):
        self.validate_snippet(self.get_snippet_path("imported_call"))

    def test_nested_import_call(self):
        self.validate_snippet(self.get_snippet_path("nested_import_call"))

    def test_call(self):
        self.validate_snippet(self.get_snippet_path("call"))
