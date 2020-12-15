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
from pycg.machinery.definitions import Definition, DefinitionManager, DefinitionError
from pycg.machinery.pointers import LiteralPointer
from pycg import utils

class DefinitionManagerTest(TestBase):
    def test_create(self):
        dm = DefinitionManager()

        dm.create("adefi", utils.constants.NAME_DEF)

        defi = dm.get("adefi")
        self.assertEqual(defi.get_type(), utils.constants.NAME_DEF)
        self.assertEqual(defi.get_ns(), "adefi")

        # only non empty strings allowed
        with self.assertRaises(DefinitionError):
            dm.create("", utils.constants.NAME_DEF)

        with self.assertRaises(DefinitionError):
            dm.create(1, utils.constants.NAME_DEF)

        # no duplicate defs
        with self.assertRaises(DefinitionError):
            dm.create("adefi", utils.constants.NAME_DEF)

        # we should provide a valid type
        with self.assertRaises(DefinitionError):
            dm.create("adefi2", "notavalidtype")

    def test_assign(self):
        dm = DefinitionManager()
        defi1 = dm.create("defi1", utils.constants.NAME_DEF)
        defi1.get_name_pointer().add("item1")
        defi1.get_name_pointer().add("item2")
        defi1.get_name_pointer().add_arg(0, "arg")

        defi2 = dm.assign("defi2", defi1)
        # should have the correct ns
        self.assertEqual(defi2.get_ns(), "defi2")
        # values should be merged
        self.assertEqual(defi2.get_type(), utils.constants.NAME_DEF)
        self.assertEqual(defi2.get_name_pointer().get(), set(["item1", "item2"]))
        self.assertEqual(defi2.get_name_pointer().get_arg(0), set(["arg"]))

        # for function defs a return def should be created too
        fndefi = dm.create("fndefi", utils.constants.FUN_DEF)
        fndefi2 = dm.assign("fndefi2", fndefi)
        return_def = dm.get("{}.{}".format("fndefi2", utils.constants.RETURN_NAME))
        self.assertIsNotNone(return_def)
        self.assertEqual(return_def.get_name_pointer().get(), set(["{}.{}".format("fndefi", utils.constants.RETURN_NAME)]))


    def test_handle_function_def(self):
        # handle parent definition
        parent_ns = "root"
        fn_name = "function"
        fn_ns = "{}.{}".format(parent_ns, fn_name)

        dm = DefinitionManager()
        dm.create("root", utils.constants.NAME_DEF)

        dm.handle_function_def(parent_ns, fn_name)

        # a definition for the function should be created
        fn_def = dm.get(fn_ns)
        self.assertIsNotNone(fn_def)
