import os

from base import TestBase

class LambdasTest(TestBase):
    def test_lambda_call(self):
        snippet_path = os.path.join(self.snippets_path, "lambda_call")
        self.validate_snippet(snippet_path)

    def test_lambda_calls_parameter(self):
        snippet_path = os.path.join(self.snippets_path, "lambda_calls_parameter")
        self.validate_snippet(snippet_path)

    def test_lambda_parameter_call(self):
        snippet_path = os.path.join(self.snippets_path, "lambda_parameter_call")
        self.validate_snippet(snippet_path)

    def test_lambda_return_call(self):
        snippet_path = os.path.join(self.snippets_path, "lambda_return_call")
        self.validate_snippet(snippet_path)
