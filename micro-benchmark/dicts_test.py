
import os

from base import TestBase

class DictsTest(TestBase):
    snippet_dir = "dicts"

    def test_type_coercion(self):
        self.validate_snippet(self.get_snippet_path("type_coercion"))

    def test_update(self):
        self.validate_snippet(self.get_snippet_path("update"))

    def test_ext_key(self):
        self.validate_snippet(self.get_snippet_path("ext_key"))

    def test_return(self):
        self.validate_snippet(self.get_snippet_path("return"))

    def test_param(self):
        self.validate_snippet(self.get_snippet_path("param"))

    def test_return_assign(self):
        self.validate_snippet(self.get_snippet_path("return_assign"))

    def test_call(self):
        self.validate_snippet(self.get_snippet_path("call"))

    def test_assign(self):
        self.validate_snippet(self.get_snippet_path("assign"))

    def test_param_key(self):
        self.validate_snippet(self.get_snippet_path("param_key"))

    def test_new_key_param(self):
        self.validate_snippet(self.get_snippet_path("new_key_param"))

    def test_nested(self):
        self.validate_snippet(self.get_snippet_path("nested"))

    def test_add_key(self):
        self.validate_snippet(self.get_snippet_path("add_key"))
