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
import sys
import copy
import mock
import os

from base import TestBase
from pycg.machinery.imports import ImportManager, ImportManagerError, get_custom_loader

class ImportsTest(TestBase):
    def test_create_node(self):
        fpath = "input_file.py"
        im = ImportManager()
        im.set_pkg("")

        name = "node1"
        im.create_node(name)
        self.assertEqual(im.get_filepath(name), "")
        self.assertEqual(im.get_imports(name), set())

        # if a node already exists it can't be added again
        with self.assertRaises(ImportManagerError):
            im.create_node(name)

        # no empty node names
        with self.assertRaises(ImportManagerError):
            im.create_node("")

        with self.assertRaises(ImportManagerError):
            im.create_node(1)

    def test_set_filepath(self):
        fpath = "input_file.py"
        im = ImportManager()
        im.set_pkg("")

        name = "node1"
        im.create_node(name)

        filepath1 = "filepath1"
        im.set_filepath(name, filepath1)
        self.assertEqual(im.get_filepath(name), os.path.abspath(filepath1))

        filepath2 = "filepath2"
        im.set_filepath(name, filepath2)
        self.assertEqual(im.get_filepath(name), os.path.abspath(filepath2))

        # only non empty strings allowed
        with self.assertRaises(ImportManagerError):
            im.set_filepath(name, "")

        with self.assertRaises(ImportManagerError):
            im.set_filepath(name, 1)

    def test_create_edge(self):
        fpath = "input_file.py"
        im = ImportManager()
        im.set_pkg("")
        node1 = "node1"
        node2 = "node2"

        im.create_node(node1)
        im.create_node(node2)

        # current module not set
        with self.assertRaises(ImportManagerError):
            im.create_edge(node2)

        im.set_current_mod(node1, fpath)
        im.create_edge(node2)

        self.assertEqual(im.get_imports(node1), set([node2]))

        # only non empty strings allowed
        with self.assertRaises(ImportManagerError):
            im.create_edge("")

        with self.assertRaises(ImportManagerError):
            im.create_edge(1)


    def test_hooks(self):
        input_file = "somedir/somedir/input_file.py"
        im = ImportManager()
        im.set_pkg("somedir/somedir")
        old_sys_path = copy.deepcopy(sys.path)
        old_path_hooks = copy.deepcopy(sys.path_hooks)
        custom_loader = "custom_loader"

        with mock.patch("importlib.machinery.FileFinder.path_hook", return_value=custom_loader):
            im.install_hooks()

        self.assertEqual(sys.path_hooks[0], custom_loader)
        self.assertEqual(sys.path[0], os.path.abspath(os.path.dirname(input_file)))

        im.remove_hooks()
        self.assertEqual(old_sys_path, sys.path)
        self.assertEqual(old_path_hooks, sys.path_hooks)

    def test_custom_loader(self):
        fpath = "input_file.py"
        im = ImportManager()
        im.set_pkg("")
        old_sys_path = copy.deepcopy(sys.path)
        im.set_current_mod("node1", fpath)
        im.create_node("node1")

        # an import happens and the loader is called
        loader = get_custom_loader(im)("node2", "filepath")

        # verify that edges and nodes have been added
        self.assertEqual(im.get_imports("node1"), set(["node2"]))
        self.assertEqual(im.get_filepath("node2"), os.path.abspath("filepath"))

        loader = get_custom_loader(im)("node2", "filepath")
        self.assertEqual(im.get_imports("node1"), set(["node2"]))
        self.assertEqual(im.get_filepath("node2"), os.path.abspath("filepath"))

        self.assertEqual(loader.get_filename("filepath"), "filepath")
        self.assertEqual(loader.get_data("filepath"), "")

    def test_handle_import_level(self):
        fpath = "input_file.py"
        im = ImportManager()
        im.set_pkg("")
        im.set_current_mod("mod1.mod2.mod3", fpath)

        # gets outside of package scope
        with self.assertRaises(ImportError):
            im._handle_import_level("something", 4)

        self.assertEqual(im._handle_import_level("smth", 2), ("..smth", "mod1"))
        self.assertEqual(im._handle_import_level("smth", 1), (".smth", "mod1.mod2"))
        self.assertEqual(im._handle_import_level("smth", 0), ("smth", ""))

    def test_handle_import(self):
        # test builtin modules
        fpath = "input_file.py"
        im = ImportManager()
        im.set_pkg("")
        im.create_node("mod1")
        im.set_current_mod("mod1", fpath)

        self.assertEqual(im.handle_import("sys", 0), None)
        self.assertEqual(im.handle_import("sys", 10), None)

        self.assertEqual(im.get_imports("mod1"), set(["sys"]))

        # test parent package
        class MockImport:
            def __init__(self, name):
                self.__file__ = name

        with mock.patch("importlib.import_module", return_value=MockImport(os.path.abspath("mod2.py"))) as mock_import:
            modname = im.handle_import("mod2", 0)
            self.assertEqual(modname, "mod2")
            mock_import.assert_called_with("mod2", package="")

        with mock.patch("importlib.import_module", return_value=MockImport(os.path.abspath("mod2.py"))) as mock_import:
            im.set_current_mod("mod1.mod3", fpath)
            modname = im.handle_import("mod2", 1)
            self.assertEqual(modname, "mod2")
            mock_import.assert_called_once_with(".mod2", package="mod1")
