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
from base import TestBase

from pycg.machinery.pointers import Pointer, NamePointer,\
    LiteralPointer, PointerError

class PointerTest(TestBase):
    def test_merge(self):
        pointer = Pointer()
        pointer2 = Pointer()
        pointer.add("smth")
        pointer.add("smth2")
        pointer2.add("smth3")
        pointer2.add("smth2")

        pointer.merge(pointer2)

        self.assertEqual(pointer.get(), set(["smth", "smth2", "smth3"]))
        self.assertEqual(pointer2.get(), set(["smth2", "smth3"]))

        pointer3 = Pointer()
        pointer.merge(pointer3)
        self.assertEqual(pointer.get(), set(["smth", "smth2", "smth3"]))
        self.assertEqual(pointer3.get(), set())

    def test_literal_pointer(self):
        pointer = LiteralPointer()
        # assert that for string values, we just include
        # that the literal points to a str or int
        clone = set(["something"])
        pointer.add("something")
        self.assertEqual(pointer.get(), clone)

        clone.add(1)
        pointer.add(1)
        self.assertEqual(pointer.get(), clone)

        clone.add(LiteralPointer.UNK_LIT)
        pointer.add({})
        self.assertEqual(pointer.get(), clone)

    def test_name_pointer(self):
        pointer = NamePointer()
        clone = {}
        name_clone = {}

        self.assertEqual(pointer.get_args(), clone)

        name_clone["name0"] = clone[0] = set(["something", "set", "addition"])
        name_clone["name1"] = clone[1] = set(["somethingelse"])

        pointer.add_pos_arg(0, "name0", "something")
        pointer.add_pos_arg(1, "name1", "somethingelse")
        pointer.add_pos_arg(0, "name0", set(["set", "addition"]))

        with self.assertRaises(PointerError):
            pointer.add_pos_arg("NaN", "NaN0", "fail")

        self.assertEqual(pointer.get_pos_args(), clone)
        self.assertEqual(pointer.get_args(), name_clone)

        name_clone["name2"] = clone[2] = set([LiteralPointer.INT_LIT])
        pointer.add_pos_lit_arg(2, "name2", 2)
        pointer.add_pos_lit_arg(2, "name2", 3)
        self.assertEqual(pointer.get_pos_args(), clone)
        self.assertEqual(pointer.get_args(), name_clone)

        clone[1].add(LiteralPointer.STR_LIT)
        name_clone["name1"] = clone[1]

        pointer.add_pos_lit_arg(1, "name1", "str")
        self.assertEqual(pointer.get_pos_args(), clone)
        self.assertEqual(pointer.get_args(), name_clone)

        with self.assertRaises(PointerError):
            pointer.add_pos_lit_arg("NaN", "NaN0", "fail")

    def test_name_pointer_merge(self):
        pointer1 = NamePointer()
        pointer1.add("smth1")
        pointer1.add_arg(0, set(["smth2", "smth3"]))
        pointer1.add_arg(1, set(["smth4"]))

        pointer2 = NamePointer()
        pointer2.add("smth6")
        pointer2.add_arg(0, set(["smth7", "smth8"]))
        pointer2.add_arg(1, set(["smth9"]))

        pointer1.merge(pointer2)

        self.assertEqual(pointer1.get(), set(["smth1", "smth6"]))
        self.assertEqual(pointer1.get_arg(0), set(["smth2", "smth3", "smth7", "smth8"]))
        self.assertEqual(pointer1.get_arg(1), set(["smth4", "smth9"]))
