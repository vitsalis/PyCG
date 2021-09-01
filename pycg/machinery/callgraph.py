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

from pycg import utils

class CallGraph(object):
    def __init__(self):
        self.cg = {}
        self.modnames = {}
        self.lines_graph = {}

    # The "-1" is passed to skip duplicated line numbers from final line graph
    def add_node(self, name, modname="", lineno="-1"):
        if not isinstance(name, str):
            raise CallGraphError("Only string node names allowed")
        if not name:
            raise CallGraphError("Empty node name")
        self.add_into_line_graph(name, lineno)
        if not name in self.cg:
            self.cg[name] = set()
            self.modnames[name] = modname

        if name in self.cg and not self.modnames[name]:
            self.modnames[name] = modname

    def add_edge(self, src, dest):
        self.add_node(src, "")
        self.add_node(dest, "")
        self.cg[src].add(dest)

    def get(self):
        return self.cg

    def get_lines_graph(self):
        return self.lines_graph

    def get_edges(self):
        output = []
        for src in self.cg:
            for dst in self.cg[src]:
                output.append([src, dst])
        return output

    def get_modules(self):
        return self.modnames

    def add_into_line_graph(self, name, lineno):
        if lineno != "-1":
            if name in self.lines_graph:
                 self.lines_graph[name].append(str(lineno))
            else:
                 self.lines_graph[name] = [str(lineno)]

class CallGraphError(Exception):
    pass
