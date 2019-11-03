import os
import sys
import importlib
import json

from unittest import TestCase, main

class TestBase(TestCase):
    def setUp(self):
        def error():
            print ("Invalid module %s.%s" % (cg_mod, cg_class))
            print ("Set environment variables `CALL_GRAPH_CLASS` and `CALL_GRAPH_MODULE` properly")
            sys.exit(1)

        self.snippets_path = os.environ.get("SNIPPETS_PATH")
        cg_class = os.environ.get('CALL_GRAPH_CLASS', None)
        cg_mod = os.environ.get('CALL_GRAPH_MODULE', None)
        if not cg_class or not cg_mod:
            error()
        try:
            self.cg_mod = importlib.import_module(cg_mod)
        except ImportError:
            error()

        self.cg_class = getattr(self.cg_mod, cg_class)
        if not self.cg_class:
            error()

    def validate_snippet(self, snippet_path):
        output = self.get_snippet_output_cg(snippet_path)
        expected = self.get_snippet_expected_cg(snippet_path)

        self.assertEqual(output, expected)

    def get_snippet_output_cg(self, snippet_path):
        main_path = os.path.join(snippet_path, "main.py")
        cg = self.cg_class(main_path)
        return cg.output()

    def get_snippet_expected_cg(self, snippet_path):
        cg_path = os.path.join(snippet_path, "callgraph.json")
        with open(cg_path, "r") as f:
            return json.loads(f.read())

    def assertEqual(self, actual, expected):
        def do_sorted(d):
            s = {}
            for n in d:
                s[n] = sorted(d[n])
            return s

        super().assertEqual(do_sorted(actual), do_sorted(expected))


if __name__ == "__main__":
    main()
