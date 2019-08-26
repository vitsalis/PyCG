import os

from base import TestBase

class FunctionsTest(TestBase):
    def test_function_call(self):
        """
        Structure: A function is defined and called.
        """
        snippet_path = os.path.join(self.snippets_path, "function_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    def test_assigned_function_call(self):
        """
        A function is defined, assigned to a variable and called
        via that variable.
        """
        snippet_path = os.path.join(self.snippets_path, "assigned_function_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    def test_parameter_function_call(self):
        """
        A function `func` is defined which takes as a parameter
        a function which it later calls.
        """
        snippet_path = os.path.join(self.snippets_path, "parameter_function_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": ["main.param_func"], "main.param_func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    def test_assigned_parameter_function_call(self):
        """
        A function `func` is defined which takes as a parameter
        a variable which has a function assigned to it which it later calls.
        """
        snippet_path = os.path.join(self.snippets_path, "assigned_parameter_function_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": ["main.param_func"], "main.param_func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    def test_nested_parameter_function_call(self):
        """
        Now the parameter function calls a nested function.
        """
        snippet_path = os.path.join(self.snippets_path, "nested_parameter_function_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": ["main.param_func"], "main.param_func": ["main.nested_func"],
            "main.nested_func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    def test_return_function_call(self):
        """
        A function `func` is called and returns a function `return_func`
        which is later called, via a variable.
        """
        snippet_path = os.path.join(self.snippets_path, "return_function_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "main.return_func": [], "main": ["main.func", "main.return_func"]}

        self.assertEqual(output, expected)

    # TODO: This fails because we haven't yet identified a way
    # to cound the number of calls using the ast.
    def test_return_function_call_direct(self):
        """
        A function `func` is called and returns a function `return_func`
        which is later called directly in the form func()().
        """
        snippet_path = os.path.join(self.snippets_path, "return_function_call_direct", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "main.return_func": [], "main": ["main.func", "main.return_func"]}

        self.assertEqual(output, expected)

    def test_builtin_function_call(self):
        """
        print is called
        """
        snippet_path = os.path.join(self.snippets_path, "builtin_function_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["<built-in>.print"]}

        self.assertEqual(output, expected)

    def test_imported_function_call(self):
        """
        Import a function from another module and call it
        """

        snippet_path = os.path.join(self.snippets_path, "imported_function_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func"], "to_import.func": []}

        self.assertEqual(output, expected)

    def test_imported_function_return_call(self):
        """
        Import a function from another module, call it, and call
        the function it returns.
        """

        snippet_path = os.path.join(self.snippets_path, "imported_function_return_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func", "to_import.return_func"], "to_import.func": [], "to_import.return_func": []}

        self.assertEqual(output, expected)

    def test_imported_function_return_call_direct(self):
        """
        Import a function from another module, call it, and call
        the function it returns.
        """

        snippet_path = os.path.join(self.snippets_path, "imported_function_return_call_direct", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func", "to_import.return_func"], "to_import.func": [], "to_import.return_func": []}

        self.assertEqual(output, expected)

    def test_imported_function_return_from_different_mod_call(self):
        """
        Import a function from another module, call it, and call
        the function it returns.
        """

        snippet_path = os.path.join(self.snippets_path, "imported_function_return_from_different_mod_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func", "to_import2.return_func"], "to_import.func": [], "to_import2.return_func": []}

        self.assertEqual(output, expected)

    def test_imported_function_with_function_parameter_call(self):
        """
        Import a function from another module and call it with a function parameter
        """

        snippet_path = os.path.join(self.snippets_path, "imported_function_with_function_parameter_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func"], "main.param_func": [], "to_import.func": ["main.param_func"]}

        self.assertEqual(output, expected)

    def test_imported_function_with_function_parameter_assigned_call(self):
        """
        Import a function from another module and call it with a function parameter
        which as been assigned to a variable.
        """

        snippet_path = os.path.join(self.snippets_path, "imported_function_with_function_parameter_assigned_call", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func"], "to_import.func": ["main.param_func"]}

        self.assertEqual(output, expected)
