
import os

from base import TestBase

class ExternalTest(TestBase):
    snippet_dir = "external"

    def test_attribute(self):
        self.validate_snippet(self.get_snippet_path("attribute"))

    def test_function_assigned(self):
        self.validate_snippet(self.get_snippet_path("function_assigned"))

    def test_attribute_assigned(self):
        self.validate_snippet(self.get_snippet_path("attribute_assigned"))

    def test_function_asname(self):
        self.validate_snippet(self.get_snippet_path("function_asname"))

    def test_function(self):
        self.validate_snippet(self.get_snippet_path("function"))

    def test_cls_parent(self):
        self.validate_snippet(self.get_snippet_path("cls_parent"))
