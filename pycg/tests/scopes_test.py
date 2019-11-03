from base import TestBase
from mock import patch

from pycg.machinery.scopes import ScopeManager, ScopeItem, ScopeError

class ScopeManagerTest(TestBase):
    pass

class ScopeItemTest(TestBase):
    def test_setup(self):
        # no issues
        scope = ScopeItem("smth", None)
        scope = ScopeItem("smth", scope)
        # starts of with empty defs
        self.assertEqual(scope.get_defs(), {})

        # only strs allowed
        with self.assertRaises(ScopeError):
            scope = ScopeItem(1, None)

        # parent needs to be a ScopeItem instance
        with self.assertRaises(ScopeError):
            scope = ScopeItem("smth", "parent")

    def test_get_ns(self):
        # test that namespace is set properly
        root_scope = ScopeItem("root", None)
        self.assertEqual(root_scope.get_ns(), "root")
        child_scope = ScopeItem("root.child", root_scope)
        self.assertEqual(child_scope.get_ns(), "root.child")

    def test_defs(self):
        class MockDef(object):
            def __init__(self):
                self.get_points_to_called = False
                self.merge_points_to_called = False

            def get_points_to(self, *args, **kwargs):
                self.get_points_to_called = True

            def merge_points_to(self, *args, **kwargs):
                self.merge_points_to_called = True

        scope = ScopeItem("smth", None)

        clone = {"adef": "definition"}

        scope.add_def("adef", "definition")
        self.assertEqual(scope.get_defs().items(), clone.items())
        self.assertEqual(scope.get_def("adef"), "definition")

        defi1 = MockDef()
        defi2 = MockDef()
        scope.add_def("defi1", defi1)

        # appropriate functions were called
        scope.merge_def("defi1", defi2)
        self.assertTrue(defi1.merge_points_to_called)
        self.assertTrue(defi2.get_points_to_called)

        # If the def doesn't exist just assign to it
        scope.merge_def("defi100", "defi1001")
        self.assertEqual(scope.get_def("defi100"), "defi1001")
