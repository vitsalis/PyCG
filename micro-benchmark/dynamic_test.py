
import os

from base import TestBase

class DynamicTest(TestBase):
    snippet_dir = "dynamic"

    def test_eval(self):
        self.validate_snippet(self.get_snippet_path("eval"))
