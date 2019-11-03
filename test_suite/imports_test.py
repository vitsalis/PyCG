import os

from base import TestBase

class ImportsTest(TestBase):
    def test_simple_import(self):
        snippet_path = os.path.join(self.snippets_path, "simple_import")
        self.validate_snippet(snippet_path)

    def test_import_as(self):
        snippet_path = os.path.join(self.snippets_path, "import_as")
        self.validate_snippet(snippet_path)

    def test_submodule_import(self):
        snippet_path = os.path.join(self.snippets_path, "submodule_import")
        self.validate_snippet(snippet_path)

    def test_submodule_import_as(self):
        snippet_path = os.path.join(self.snippets_path, "submodule_import_as")
        self.validate_snippet(snippet_path)

    def test_import_from(self):
        snippet_path = os.path.join(self.snippets_path, "import_from")
        self.validate_snippet(snippet_path)

    def test_import_all(self):
        snippet_path = os.path.join(self.snippets_path, "import_all")
        self.validate_snippet(snippet_path)

    def test_submodule_import_from(self):
        snippet_path = os.path.join(self.snippets_path, "submodule_import_from")
        self.validate_snippet(snippet_path)

    def test_submodule_import_all(self):
        snippet_path = os.path.join(self.snippets_path, "submodule_import_all")
        self.validate_snippet(snippet_path)

    def test_chained_import(self):
        snippet_path = os.path.join(self.snippets_path, "chained_import")
        self.validate_snippet(snippet_path)

    def test_relative_import(self):
        snippet_path = os.path.join(self.snippets_path, "relative_import")
        self.validate_snippet(snippet_path)

    def test_relative_import_with_name(self):
        snippet_path = os.path.join(self.snippets_path, "relative_import_with_name")
        self.validate_snippet(snippet_path)

    def test_parent_import(self):
        snippet_path = os.path.join(self.snippets_path, "parent_import")
        self.validate_snippet(snippet_path)
