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
from pycg.machinery.callgraph import CallGraph, CallGraphError

class CallGraphTest(TestBase):
    def setUp(self):
        self.cg = CallGraph()

    def tearDown(self):
        del self.cg

    def test_setup(self):
        self.assertEqual(self.cg.get(), {})

    def test_add_node(self):
        clone = {}

        self.cg.add_node("node1")
        clone["node1"] = set()
        self.assertEqual(self.cg.get().items(), clone.items())

        # no duplicate nodes
        self.cg.add_node("node1")
        self.assertEqual(self.cg.get().items(), clone.items())

        # only str types can be mapped
        with self.assertRaises(CallGraphError):
            self.cg.add_node(1)

        # no empty names allowed
        with self.assertRaises(CallGraphError):
            self.cg.add_node("")

        self.cg.add_node("node2")
        clone["node2"] = set()
        self.assertEqual(self.cg.get().items(), clone.items())

    def test_add_edge(self):
        clone = {}
        clone["node1"] = set(["node2"])
        clone["node2"] = set()

        # should create a node for node1 and node2
        # and add an edge from node1 to node2
        self.cg.add_edge("node1", "node2")
        self.assertEqual(self.cg.get().items(), clone.items())

        # no duplicate items
        self.cg.add_edge("node1", "node2")
        self.assertEqual(self.cg.get().items(), clone.items())

        clone["node2"].add("node1")
        self.cg.add_edge("node2", "node1")
        self.assertEqual(self.cg.get().items(), clone.items())

        # no integer nodes allowed
        with self.assertRaises(CallGraphError):
            self.cg.add_edge("node1", 1)
        with self.assertRaises(CallGraphError):
            self.cg.add_edge(1, "node1")

        # no empty strings allowed
        with self.assertRaises(CallGraphError):
            self.cg.add_edge("node1", "")
        with self.assertRaises(CallGraphError):
            self.cg.add_edge("", "node1")
