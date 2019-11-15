import os

from base import TestBase

class FunctionsTest(TestBase):
    def test_function_call(self):
        snippet_path = os.path.join(self.snippets_path, "function_call")
        self.validate_snippet(snippet_path)

    def test_assigned_function_call(self):
        snippet_path = os.path.join(self.snippets_path, "assigned_function_call")
        self.validate_snippet(snippet_path)

    def test_parameter_function_call(self):
        snippet_path = os.path.join(self.snippets_path, "parameter_function_call")
        self.validate_snippet(snippet_path)

    def test_assigned_parameter_function_call(self):
        snippet_path = os.path.join(self.snippets_path, "assigned_parameter_function_call")
        self.validate_snippet(snippet_path)

    def test_nested_parameter_function_call(self):
        snippet_path = os.path.join(self.snippets_path, "nested_parameter_function_call")
        self.validate_snippet(snippet_path)

    def test_return_function_call(self):
        snippet_path = os.path.join(self.snippets_path, "return_function_call")
        self.validate_snippet(snippet_path)

    def test_imported_function_call(self):
        snippet_path = os.path.join(self.snippets_path, "imported_function_call")
        self.validate_snippet(snippet_path)

    def test_imported_function_return_call(self):
        snippet_path = os.path.join(self.snippets_path, "imported_function_return_call")
        self.validate_snippet(snippet_path)

    def test_imported_function_return_from_different_mod_call(self):
        snippet_path = os.path.join(self.snippets_path, "imported_function_return_from_different_mod_call")
        self.validate_snippet(snippet_path)

    def test_imported_function_with_function_parameter_call(self):
        snippet_path = os.path.join(self.snippets_path, "imported_function_with_function_parameter_call")
        self.validate_snippet(snippet_path)

    def test_imported_function_with_function_parameter_assigned_call(self):
        snippet_path = os.path.join(self.snippets_path, "imported_function_with_function_parameter_assigned_call")
        self.validate_snippet(snippet_path)

    def test_map_call(self):
        snippet_path = os.path.join(self.snippets_path, "map_call")
        self.validate_snippet(snippet_path)

    # TODO: This fails because we haven't yet identified a way
    # to cound the number of calls using the ast.
    def test_return_function_call_direct(self):
        snippet_path = os.path.join(self.snippets_path, "return_function_call_direct")
        self.validate_snippet(snippet_path)

    def test_imported_function_return_call_direct(self):
        snippet_path = os.path.join(self.snippets_path, "imported_function_return_call_direct")
        self.validate_snippet(snippet_path)

    def test_assigned_function_call_with_lit_param(self):
        snippet_path = os.path.join(self.snippets_path, "assigned_function_call_with_lit_param")
        self.validate_snippet(snippet_path)

    def test_function_return_complex(self):
        snippet_path = os.path.join(self.snippets_path, "assigned_function_return_complex")
        self.validate_snippet(snippet_path)

    def test_function_call_with_kwargs(self):
        snippet_path = os.path.join(self.snippets_path, "function_call_with_kwargs")
        self.validate_snippet(snippet_path)

    def test_function_call_with_kwargs_chained(self):
        snippet_path = os.path.join(self.snippets_path, "function_call_with_kwargs_chained")
        self.validate_snippet(snippet_path)

    def test_function_call_with_assigned_kwarg(self):
        snippet_path = os.path.join(self.snippets_path, "function_call_with_assigned_kwarg")
        self.validate_snippet(snippet_path)
