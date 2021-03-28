
import os

from base import TestBase

class GeneratorsTest(TestBase):
    snippet_dir = "generators"

    def test_iter_param(self):
        self.validate_snippet(self.get_snippet_path("iter_param"))

    def test_no_iter(self):
        self.validate_snippet(self.get_snippet_path("no_iter"))

    def test_iter_return(self):
        self.validate_snippet(self.get_snippet_path("iter_return"))

    def test_iterable(self):
        self.validate_snippet(self.get_snippet_path("iterable"))

    def test_iterable_assigned(self):
        self.validate_snippet(self.get_snippet_path("iterable_assigned"))

    def test_yield(self):
        self.validate_snippet(self.get_snippet_path("yield"))
