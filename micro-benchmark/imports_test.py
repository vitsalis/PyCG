
import os

from base import TestBase

class ImportsTest(TestBase):
    snippet_dir = "imports"

    def test_relative_import_with_name(self):
        self.validate_snippet(self.get_snippet_path("relative_import_with_name"))

    def test_submodule_import_from(self):
        self.validate_snippet(self.get_snippet_path("submodule_import_from"))

    def test_import_as(self):
        self.validate_snippet(self.get_snippet_path("import_as"))

    def test_submodule_import_all(self):
        self.validate_snippet(self.get_snippet_path("submodule_import_all"))

    def test_parent_import(self):
        self.validate_snippet(self.get_snippet_path("parent_import"))

    def test_chained_import(self):
        self.validate_snippet(self.get_snippet_path("chained_import"))

    def test_init_func_import(self):
        self.validate_snippet(self.get_snippet_path("init_func_import"))

    def test_submodule_import_as(self):
        self.validate_snippet(self.get_snippet_path("submodule_import_as"))

    def test_relative_import(self):
        self.validate_snippet(self.get_snippet_path("relative_import"))

    def test_import_all(self):
        self.validate_snippet(self.get_snippet_path("import_all"))

    def test_simple_import(self):
        self.validate_snippet(self.get_snippet_path("simple_import"))

    def test_init_import(self):
        self.validate_snippet(self.get_snippet_path("init_import"))

    def test_submodule_import(self):
        self.validate_snippet(self.get_snippet_path("submodule_import"))

    def test_import_from(self):
        self.validate_snippet(self.get_snippet_path("import_from"))
