
import os

from base import TestBase

class KwargsTest(TestBase):
    snippet_dir = "kwargs"

    def test_chained_call(self):
        self.validate_snippet(self.get_snippet_path("chained_call"))

    def test_assigned_call(self):
        self.validate_snippet(self.get_snippet_path("assigned_call"))

    def test_call(self):
        self.validate_snippet(self.get_snippet_path("call"))
