import os

from base import TestBase

class FunctionsTest(TestBase):
    def test_function_call(self):
        """
        Structure: A function is defined and called.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet12", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    def test_assigned_function_call(self):
        """
        A function is defined, assigned to a variable and called
        via that variable.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet13", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    def test_parameter_function_call(self):
        """
        A function `func` is defined which takes as a parameter
        a function which it later calls.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet14", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": ["main.param_func"], "main.param_func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    def test_assigned_parameter_function_call(self):
        """
        A function `func` is defined which takes as a parameter
        a variable which has a function assigned to it which it later calls.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet15", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main.func": ["main.param_func"], "main.param_func": [], "main": ["main.func"]}

        self.assertEqual(output, expected)

    # TODO: This doesn't work
    # a possible solution would be visiting the ast N times
    # where N is the length of the longest path in the graph
    def test_nested_parameter_function_call(self):
        """
        Now the parameter function calls a nested function.
        """
        #snippet_path = os.path.join(self.snippets_path, "snippet16", "main.py")

        #output = self.get_snippet_output_cg(snippet_path)
        #expected = {"main.func": ["main.param_func"], "main.param_func": ["main.nested_func"],
        #    "main.nested_func": [], "main": ["main.func"]}

        #self.assertEqual(output, expected)

    def test_return_function_call(self):
        """
        A function `func` is called and returns a function `return_func`
        which is later called, via a variable.
        """
        snippet_path = os.path.join(self.snippets_path, "snippet17", "main.py")

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
        #snippet_path = os.path.join(self.snippets_path, "snippet18", "main.py")

        #output = self.get_snippet_output_cg(snippet_path)
        #expected = {"main.func": [], "main.return_func": [], "main": ["main.func", "main.return_func"]}

        #self.assertEqual(output, expected)

    def test_built_in_function_call(self):
        """
        print is called
        """
        #snippet_path = os.path.join(self.snippets_path, "snippet19", "main.py")

        #output = self.get_snippet_output_cg(snippet_path)
        #expected = {"main": ["<build-in>.print"]}

        #self.assertEqual(output, expected)

    def test_imported_func(self):
        """
        Import a function from another module and call it
        """

        snippet_path = os.path.join(self.snippets_path, "snippet20", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func"], "to_import.func": []}

        self.assertEqual(output, expected)

    def test_imported_func_that_returns(self):
        """
        Import a function from another module, call it, and call
        the function it returns.
        """

        snippet_path = os.path.join(self.snippets_path, "snippet21", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func", "to_import.return_func"], "to_import.func": [], "to_import.return_func": []}

        self.assertEqual(output, expected)

    # TODO: Same as return_function_call_direct
    def test_imported_func_that_returns_direct(self):
        """
        Import a function from another module, call it, and call
        the function it returns.
        """

        #snippet_path = os.path.join(self.snippets_path, "snippet24", "main.py")

        #output = self.get_snippet_output_cg(snippet_path)
        #expected = {"main": ["to_import.func", "to_import.return_func"], "to_import.func": [], "to_import.return_func": []}

        #self.assertEqual(output, expected)

    def test_imported_func_that_returns_from_another_mod(self):
        """
        Import a function from another module, call it, and call
        the function it returns.
        """

        snippet_path = os.path.join(self.snippets_path, "snippet25", "main.py")

        output = self.get_snippet_output_cg(snippet_path)
        expected = {"main": ["to_import.func", "to_import2.return_func"], "to_import.func": [], "to_import2.return_func": []}

        self.assertEqual(output, expected)

    # TODO
    def test_call_imported_func_with_func_param(self):
        """
        Import a function from another module and call it with a function parameter
        """

        #snippet_path = os.path.join(self.snippets_path, "snippet22", "main.py")

        #output = self.get_snippet_output_cg(snippet_path)
        #expected = {"main": ["to_import.func"], "main.param_func": [], "to_import.func": ["main.param_func"]}

        #self.assertEqual(output, expected)

    # TODO
    def test_call_imported_func_with_func_param_assigned(self):
        """
        Import a function from another module and call it with a function parameter
        which as been assigned to a variable.
        """

        #snippet_path = os.path.join(self.snippets_path, "snippet23", "main.py")

        #output = self.get_snippet_output_cg(snippet_path)
        #expected = {"main": ["to_import.func"], "to_import.func": ["main.param_func"]}

        #self.assertEqual(output, expected)
