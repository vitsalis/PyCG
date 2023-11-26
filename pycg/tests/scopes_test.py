#
# Copyright (c) 2020 Vitalis Salis.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import symtable

from base import TestBase
from mock import patch

from pycg.machinery.scopes import ScopeError, ScopeItem, ScopeManager


class ScopeManagerTest(TestBase):
    def test_handle_module(self):
        class MockTable(object):
            def __init__(self, name, t, children=[], lineno=0):
                self.name = name
                self.type = t
                self.children = children
                self.lineno = lineno

            def get_type(self):
                return self.type

            def get_name(self):
                return self.name

            def get_children(self):
                return self.children

            def get_lineno(self):
                return self.lineno

        grndchld1 = MockTable("grndchld1", "variable", [])
        grndchld2 = MockTable("grndchld2", "function", [])
        chld1 = MockTable("chld1", "function", [grndchld1, grndchld2])
        grndchld3 = MockTable("grndchld3", "variable", [])
        chld2 = MockTable("chld2", "function", [grndchld3])
        grndchld4 = MockTable("grndchld4", "function", [])
        chld3 = MockTable("chld3", "class", [grndchld4])
        root = MockTable("top", "module", [chld1, chld2, chld3])

        sm = ScopeManager()
        with patch.object(symtable, "symtable", return_value=root):
            items = sm.handle_module("root", "", "")

        self.assertEqual(
            sorted(items["functions"]),
            sorted([
                "root.chld1",
                "root.chld1.grndchld2",
                "root.chld2",
                "root.chld3.grndchld4",
            ]),
        )
        self.assertEqual(sorted(items["classes"]), sorted(["root.chld3"]))

        self.assertEqual(sm.get_scope("root").get_ns(), "root")
        self.assertEqual(sm.get_scope("root").parent, None)

        self.assertEqual(sm.get_scope("root.chld1").get_ns(), "root.chld1")
        self.assertEqual(sm.get_scope("root.chld1").parent, sm.get_scope("root"))

        self.assertEqual(sm.get_scope("root.chld2").get_ns(), "root.chld2")
        self.assertEqual(sm.get_scope("root.chld2").parent, sm.get_scope("root"))

        self.assertEqual(sm.get_scope("root.chld3").get_ns(), "root.chld3")
        self.assertEqual(sm.get_scope("root.chld3").parent, sm.get_scope("root"))

        self.assertEqual(
            sm.get_scope("root.chld1.grndchld1").get_ns(), "root.chld1.grndchld1"
        )
        self.assertEqual(
            sm.get_scope("root.chld1.grndchld1").parent, sm.get_scope("root.chld1")
        )

        self.assertEqual(
            sm.get_scope("root.chld1.grndchld2").get_ns(), "root.chld1.grndchld2"
        )
        self.assertEqual(
            sm.get_scope("root.chld1.grndchld2").parent, sm.get_scope("root.chld1")
        )

        self.assertEqual(
            sm.get_scope("root.chld2.grndchld3").get_ns(), "root.chld2.grndchld3"
        )
        self.assertEqual(
            sm.get_scope("root.chld2.grndchld3").parent, sm.get_scope("root.chld2")
        )

    def test_handle_assign(self):
        sm = ScopeManager()

        sm.scopes["root"] = ScopeItem("root", None)
        sm.handle_assign("root", "name", "value")
        self.assertEqual(sm.get_def("root", "name"), "value")

    def test_get_def(self):
        sm = ScopeManager()
        root = "ns"
        chld1 = "ns.chld1"
        chld2 = "ns.chld2"
        grndchld = "ns.chld1.chld1"
        sm.scopes[root] = ScopeItem(root, None)  # root scope
        sm.scopes[chld1] = ScopeItem(chld1, sm.scopes[root])  # 1st child scope
        sm.scopes[chld2] = ScopeItem(chld2, sm.scopes[root])  # 2nd child scope
        sm.scopes[grndchld] = ScopeItem(grndchld, sm.scopes[chld1])  # grandchild

        grndchld_def = ("var", "grndchild_def")  # name, value
        chld1_def1 = ("var", "chld1_def")
        chld1_def2 = ("other_var", "chld1_other_def")
        chld2_def = ("some_var", "chld2_some_var")
        root_def = ("var", "root_var")

        sm.scopes[root].add_def(root_def[0], root_def[1])
        sm.scopes[chld2].add_def(chld2_def[0], chld2_def[1])
        sm.scopes[chld1].add_def(chld1_def1[0], chld1_def1[1])
        sm.scopes[chld1].add_def(chld1_def2[0], chld1_def2[1])
        sm.scopes[grndchld].add_def(grndchld_def[0], grndchld_def[1])

        # should be able to find a variable defined in its scope
        # also it should get the value of the nearest scope, meaning it's own
        self.assertEqual(sm.get_def("ns.chld1.chld1", grndchld_def[0]), grndchld_def[1])
        # if it doesn't exist get the parent's
        self.assertEqual(sm.get_def("ns.chld1.chld1", chld1_def2[0]), chld1_def2[1])
        # it shouldn't be able to reach a def defined in chld2
        self.assertEqual(sm.get_def("ns.chld1.chld1", chld2_def[0]), None)
        # root doesn't have access to variables defined in lower scopes
        self.assertEqual(sm.get_def("ns", chld1_def2[0]), None)
        # but childs have access to root
        self.assertEqual(sm.get_def("ns.chld2", root_def[0]), root_def[1])

    def test_get_scope(self):
        sm = ScopeManager()
        st = ScopeItem("ns", None)
        st2 = ScopeItem("ns.ns2", st)

        sm.scopes["ns"] = st
        # if it exists it should be returned
        self.assertEqual(sm.get_scope("ns"), st)
        sm.scopes["ns.ns2"] = st2
        self.assertEqual(sm.get_scope("ns.ns2"), st2)
        # otherwise None should be returned
        self.assertEqual(sm.get_scope("notexist"), None)


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
