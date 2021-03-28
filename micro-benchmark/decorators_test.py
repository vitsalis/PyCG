
import os

from base import TestBase

class DecoratorsTest(TestBase):
    snippet_dir = "decorators"

    def test_return_different_func(self):
        self.validate_snippet(self.get_snippet_path("return_different_func"))

    def test_param_call(self):
        self.validate_snippet(self.get_snippet_path("param_call"))

    def test_nested_decorators(self):
        self.validate_snippet(self.get_snippet_path("nested_decorators"))

    def test_assigned(self):
        self.validate_snippet(self.get_snippet_path("assigned"))

    def test_return(self):
        self.validate_snippet(self.get_snippet_path("return"))

    def test_call(self):
        self.validate_snippet(self.get_snippet_path("call"))

    def test_nested(self):
        self.validate_snippet(self.get_snippet_path("nested"))
