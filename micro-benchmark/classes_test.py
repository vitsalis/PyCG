
import os

from base import TestBase

class ClassesTest(TestBase):
    snippet_dir = "classes"

    def test_imported_call_without_init(self):
        self.validate_snippet(self.get_snippet_path("imported_call_without_init"))

    def test_direct_call(self):
        self.validate_snippet(self.get_snippet_path("direct_call"))

    def test_return_call_direct(self):
        self.validate_snippet(self.get_snippet_path("return_call_direct"))

    def test_nested_class_calls(self):
        self.validate_snippet(self.get_snippet_path("nested_class_calls"))

    def test_super_class_return(self):
        self.validate_snippet(self.get_snippet_path("super_class_return"))

    def test_base_class_calls_child(self):
        self.validate_snippet(self.get_snippet_path("base_class_calls_child"))

    def test_tuple_assignment(self):
        self.validate_snippet(self.get_snippet_path("tuple_assignment"))

    def test_return_call(self):
        self.validate_snippet(self.get_snippet_path("return_call"))

    def test_nested_call(self):
        self.validate_snippet(self.get_snippet_path("nested_call"))

    def test_imported_attr_access(self):
        self.validate_snippet(self.get_snippet_path("imported_attr_access"))

    def test_assigned_call(self):
        self.validate_snippet(self.get_snippet_path("assigned_call"))

    def test_self_assign_func(self):
        self.validate_snippet(self.get_snippet_path("self_assign_func"))

    def test_imported_call(self):
        self.validate_snippet(self.get_snippet_path("imported_call"))

    def test_base_class_attr(self):
        self.validate_snippet(self.get_snippet_path("base_class_attr"))

    def test_static_method_call(self):
        self.validate_snippet(self.get_snippet_path("static_method_call"))

    def test_call(self):
        self.validate_snippet(self.get_snippet_path("call"))

    def test_instance(self):
        self.validate_snippet(self.get_snippet_path("instance"))

    def test_imported_nested_attr_access(self):
        self.validate_snippet(self.get_snippet_path("imported_nested_attr_access"))

    def test_parameter_call(self):
        self.validate_snippet(self.get_snippet_path("parameter_call"))

    def test_self_assignment(self):
        self.validate_snippet(self.get_snippet_path("self_assignment"))

    def test_self_call(self):
        self.validate_snippet(self.get_snippet_path("self_call"))

    def test_assigned_self_call(self):
        self.validate_snippet(self.get_snippet_path("assigned_self_call"))
