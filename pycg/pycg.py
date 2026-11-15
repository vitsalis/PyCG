#
# Copyright (c) 2026 Vitalis Salis.
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
"""The entry point of the library: analyse a program and report the results.

All outputs are sorted, so they do not depend on the order of analysis.
"""

from pycg.analysis.program import Program
from pycg.analysis.solver import DEFAULT_CAP
from pycg.formats import edges
from pycg.formats.document import build


class CallGraphGenerator:
    """Generate the call graph of the code reachable from `entry_points`.

    `package` is the package root: module names are relative to it and only
    modules under it are analysed. Without it, the root is the deepest
    directory that contains every entry point.

    `cap` is the most objects that the analysis keeps for one variable or
    expression: past it the value is unknown, and calls through it are
    unresolved (`saturated`). It is a positive integer, or None for no cap,
    with which the analysis may not end, or run out of memory, on large
    inputs.
    """

    def __init__(self, entry_points, package=None, cap=DEFAULT_CAP):
        if cap is not None and (type(cap) is not int or cap < 1):
            raise ValueError(f"cap must be a positive integer or None, not {cap!r}")
        self.entry_points = entry_points
        self.package = package
        self.cap = cap
        self.program = None

    def analyze(self):
        self.program = Program(self.entry_points, self.package, self.cap)
        self.program.analyse()

    def document(self, package_name=None, package_version=None):
        """The document of the analysis (docs/format.md); `package_name`
        and `package_version` name the analysed package."""
        return build(self.program, package_name, package_version)

    def output(self):
        """The call graph: each node mapped to the sorted names it calls,
        the edges of the document (see `pycg.formats.edges`).

        The nodes are the analysed modules, every function and lambda they
        define, and every callee.
        """
        return edges(self.document())

    def output_points_to(self):
        """The assignment graph: each variable, field and return value with
        the sorted names of the objects it may hold; a saturated node holds
        none that it can name. For tests: the document does not show it."""
        points_to = {}
        analysis = self.program.analysis
        for node in analysis.named_nodes:
            names = points_to.setdefault(node.label, set())
            names.update(
                obj.name
                for obj in analysis.solver.objects(node)
                if obj is not analysis.saturated
            )
        return {label: sorted(points_to[label]) for label in sorted(points_to)}
