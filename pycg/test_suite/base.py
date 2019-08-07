import os
import sys
import importlib

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

    def get_snippet_output_cg(self, snippet_path):
        cg = self.cg_class("main", snippet_path)
        cg.analyze()
        return cg.output_call_graph()

    def assertEqual(self, actual, expected):
        def do_sorted(d):
            s = {}
            for n in d:
                s[n] = sorted(d[n])
            return s

        super().assertEqual(do_sorted(actual), do_sorted(expected))


if __name__ == "__main__":
    main()
