import os

from base import TestBase

class ImportsTest(TestBase):
    def test_simple_import(self):
        """
        Structure: The `main` module imports `to_import` module.
        `to_import` module defines a function which is
        called.
        Expected: The call graphs for the `main` module and `to_import`
        should be merged.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet1", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "to_import.func": []}

        self.assertEqual(output, expected)

    def test_import_as(self):
        """
        Structure: The `main` module imports `to_import` as `as_import_name`.
        `to_import` defines a function.
        Expected: The call graphs for `main` and `to_import` should be merged
        """
        snippet_path = os.path.join(self.snippets_path, "snippet2", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "to_import.func": []}

        self.assertEqual(output, expected)

    def test_submodule_import(self):
        """
        Structure: The `main` module imports `to_import.to_import` module.
        `to_import` module has an `__init__` file which defines and calls a function.
        `to_import.to_import` module defines and calls a function too.
        Expected: The call graphs for `main`, `to_import.__init__` and `to_import.to_import`
        should be merged.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet3", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "to_import.__init__.func": [], "to_import.to_import.func": []}

        self.assertEqual(output, expected)

    def test_submodule_import_as(self):
        """
        Same concept as with `test_import_as` but with a submodule
        """
        snippet_path = os.path.join(self.snippets_path, "snippet4", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "to_import.__init__.func": [], "to_import.to_import.func": []}

        self.assertEqual(output, expected)

    def test_import_from(self):
        """
        Structure: The `main` module imports `func` from `from_module`
        which defines a function. This function is then called by `main`
        Expected: An edge from `main` to `from_module.func`
        """
        snippet_path = os.path.join(self.snippets_path, "snippet5", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["from_module.func"], "from_module.func": []}

        self.assertEqual(output, expected)

    def test_import_all(self):
        """
        Structure: The `main` module imports all functions of `from_module`,
        in this case `func1` and `func2`.
        These functions are called by `main`.
        Expected: Edges from `main` to those functions
        """
        snippet_path = os.path.join(self.snippets_path, "snippet6", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["from_module.func1", "from_module.func2"], "from_module.func1": [], "from_module.func2": []}

        self.assertEqual(output, expected)

    def test_submodule_import_from(self):
        """
        Same concept as `test_import_from` but with a submodule.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet7", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {
            "main": ["from_module.nested_module.func1", "from_module.nested_module.func2"],
            "from_module.nested_module.func1": [],
            "from_module.nested_module.func2": []
        }

        self.assertEqual(output, expected)

    def test_submodule_import_all(self):
        """
        Same concept as `test_import_all` but with a submodule
        """
        snippet_path = os.path.join(self.snippets_path, "snippet8", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {
            "main": ["from_module.nested_module.func1", "from_module.nested_module.func2"],
            "from_module.nested_module.func1": [],
            "from_module.nested_module.func2": []
        }

        self.assertEqual(output, expected)

    def test_chained_import(self):
        """
        Structure: The `main` module imports `to_import` module which imports
        the `chained_import` module, which defines a function `func1`.
        `to_import` defines a function `func2` that calls `func1` and
        then `main` calls `func2`.
        Expected: An edge from `main` to `func2` and from `func2` to `func1`.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet9", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {
            "main": ["from_import.func2"],
            "from_import.func2": ["chained_import.func1"],
            "chained_import.func1": []
        }

        self.assertEqual(output, expected)

    def test_relative_import(self):
        """
        Structure: The `main` module imports the `nested.to_import` module
        which in turn imports `nested.to_import2` via a relative path.
        We define functions accordingly with `test_chained_import`.
        The import is of the form `from . import to_import`.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet10", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "to_import.func": []}

        self.assertEqual(output, expected)

    def test_relative_import_with_name(self):
        """
        Same as before but the import is of the form
        `from .to_import2 import func2`
        """
        snippet_path = os.path.join(self.snippets_path, "snippet11", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {
            "main": ["nested.to_import.func1"],
            "nested.to_import.func1": ["nested.relative.func2"],
            "nested.relative.func2": []
        }

        self.assertEqual(output, expected)

    # TODO
    def test_parent_import(self):
        """
        Structure: The `main` module imports `nested.to_import` module
        and this module in turn imports `to_import2` via the command
        `from .. import to_import2`
        Expected: An edge from nested.nested2.to_import to the function
        defined in nested.to_import2.
        """
        #snippet_path = os.path.join(self.snippets_path, "snippet12", "main.py")

        #output = self.get_snippet_output_cg(snippet_path)
        #expected = {
        #    "main.func": [],
        #    "nested.to_import.func": [],
        #    "to_import2.func": []
        #}

        #self.assertEqual(output, expected)
