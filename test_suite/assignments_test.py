import os

from base import TestBase

class AssignmentsTest(TestBase):
    def test_chained_assignment(self):
        snippet_path = os.path.join(self.snippets_path, "chained_assignment")
        self.validate_snippet(snippet_path)

    def test_starred_assignment(self):
        snippet_path = os.path.join(self.snippets_path, "starred_assignment")
        self.validate_snippet(snippet_path)

    def test_tuple_assignment(self):
        snippet_path = os.path.join(self.snippets_path, "tuple_assignment")
        self.validate_snippet(snippet_path)

    def test_recursive_tuple_assignment(self):
        snippet_path = os.path.join(self.snippets_path, "recursive_tuple_assignment")
        self.validate_snippet(snippet_path)

    def test_list_assignment_call(self):
        snippet_path = os.path.join(self.snippets_path, "list_assignment_call")
        self.validate_snippet(snippet_path)
