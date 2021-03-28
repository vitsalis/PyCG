
import os

from base import TestBase

class MroTest(TestBase):
    snippet_dir = "mro"

    def test_basic_init(self):
        self.validate_snippet(self.get_snippet_path("basic_init"))

    def test_parents_same_superclass(self):
        self.validate_snippet(self.get_snippet_path("parents_same_superclass"))

    def test_basic(self):
        self.validate_snippet(self.get_snippet_path("basic"))

    def test_two_parents(self):
        self.validate_snippet(self.get_snippet_path("two_parents"))

    def test_super_call(self):
        self.validate_snippet(self.get_snippet_path("super_call"))

    def test_self_assignment(self):
        self.validate_snippet(self.get_snippet_path("self_assignment"))

    def test_two_parents_method_defined(self):
        self.validate_snippet(self.get_snippet_path("two_parents_method_defined"))
