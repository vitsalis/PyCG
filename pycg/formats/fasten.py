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
import os
import re

from pycg import utils

from .base import BaseFormatter

# A PEP 508 requirement: a name, optional extras, version specifiers or a
# direct reference ("name @ url"), and an optional environment marker.
_REQUIREMENT = re.compile(
    r"""
    (?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)
    \s*(?:\[[^\]]*\])?
    \s*(?:@\s*\S+|\(?(?P<specs>[^;()]*)\)?)
    \s*(?:;.*)?
    """,
    re.VERBOSE,
)
_SPECIFIER = re.compile(r"\s*(===|==|!=|~=|<=|>=|<|>)\s*([A-Za-z0-9][^\s,;()]*)\s*")


def _parse_requirement(line):
    """Parse a requirements.txt line into (name, [(operator, version), ...]).

    Return None if the line is not a requirement, for example an option
    such as "-e .", a comment or a URL.
    """
    line = line.partition(" #")[0].strip()
    match = _REQUIREMENT.fullmatch(line)
    if not match:
        return None

    specs = []
    if match["specs"] and match["specs"].strip():
        spec_texts = match["specs"].split(",")
        # One trailing comma is allowed.
        if not spec_texts[-1].strip():
            spec_texts.pop()
        for spec in spec_texts:
            spec_match = _SPECIFIER.fullmatch(spec)
            if not spec_match:
                return None
            specs.append(spec_match.groups())

    return match["name"], specs


class Fasten(BaseFormatter):
    def __init__(self, cg_generator, package, product, forge, version, timestamp):
        self.cg_generator = cg_generator
        self.internal_mods = self.cg_generator.output_internal_mods() or {}
        self.external_mods = self.cg_generator.output_external_mods() or {}
        self.classes = self.cg_generator.output_classes() or {}
        self.edges = self.cg_generator.output_edges() or []
        self.functions = self.cg_generator.output_functions() or []
        self.unique = 0
        self.namespace_map = {}
        self.package = package
        self.product = product
        self.forge = forge
        self.version = version
        self.timestamp = timestamp

    def get_unique_and_increment(self):
        unique = self.unique
        self.unique += 1
        return unique

    def to_uri(self, modname, name=""):
        cleared = name
        if name:
            if name == modname:
                cleared = ""
            else:
                if not name.startswith(modname + "."):
                    raise Exception("name should start with modname", name, modname)

                cleared = name[(len(modname) + 1) :]

        suffix = ""
        if name in self.functions:
            suffix = "()"

        return "/{}/{}{}".format(modname.replace("-", "_"), cleared, suffix)

    def to_external_uri(self, modname, name=""):
        if modname == utils.constants.BUILTIN_NAME:
            name = name[len(modname) + 1 :]
            modname = ".builtin"

        return "//{}//{}".format(modname.replace("-", "_"), name)

    def find_dependencies(self, package_path):
        res = []
        if not package_path:
            return res
        requirements_path = os.path.join(package_path, "requirements.txt")

        if not os.path.exists(requirements_path):
            return res

        with open(requirements_path, "r") as f:
            lines = [_l.strip() for _l in f.readlines()]

        for line in lines:
            if not line:
                continue

            requirement = _parse_requirement(line)
            if requirement is None:
                # The specific line in the requirements.txt
                # does not follow the Requirements File Format
                continue

            name, specs = requirement

            constraints = []

            def add_range(begin, end):
                if begin and end:
                    if begin[1] and end[1]:
                        constraints.append("[{}..{}]".format(begin[0], end[0]))
                    elif begin[1]:
                        constraints.append("[{}..{})".format(begin[0], end[0]))
                    elif end[1]:
                        constraints.append("({}..{}]".format(begin[0], end[0]))
                    else:
                        constraints.append("({}..{})".format(begin[0], end[0]))
                elif begin:
                    if begin[1]:
                        constraints.append("[{}..]".format(begin[0]))
                    else:
                        constraints.append("({}..]".format(begin[0]))
                elif end:
                    if end[1]:
                        constraints.append("[..{}]".format(end[0]))
                    else:
                        constraints.append("[..{})".format(end[0]))

            begin = None
            end = None
            for key, val in sorted(specs, key=lambda x: x[1]):
                # if begin, then it is already in a range
                if key == "==":
                    if begin and end:
                        add_range(begin, end)
                        begin = None
                        end = None
                    if not begin:
                        constraints.append("[{}]".format(val))

                if key == ">":
                    if end:
                        add_range(begin, end)
                        end = None
                        begin = None
                    if not begin:
                        begin = (val, False)
                if key == ">=":
                    if end:
                        add_range(begin, end)
                        begin = None
                        end = None
                    if not begin:
                        begin = (val, True)

                if key == "<":
                    end = (val, False)
                if key == "<=":
                    end = (val, True)
            add_range(begin, end)

            res.append({"forge": "PyPI", "product": name, "constraints": constraints})

        return res

    def get_internal_modules(self):
        mods = {}

        for modname, module in self.internal_mods.items():
            name = self.to_uri(modname)
            filename = module["filename"]
            namespaces = module["methods"]

            mods[name] = {"sourceFile": filename, "namespaces": {}}

            for namespace, info in namespaces.items():
                namespace_uri = self.to_uri(modname, info["name"])

                unique = self.get_unique_and_increment()
                mods[name]["namespaces"][unique] = dict(
                    namespace=namespace_uri,
                    metadata=dict(first=info["first"], last=info["last"]),
                )
                self.namespace_map[namespace_uri] = unique
        mods = self.add_superclasses(mods)

        return mods

    def add_superclasses(self, mods):
        for cls_name, cls in self.classes.items():
            cls_uri = self.namespace_map.get(self.to_uri(cls["module"], cls_name))
            mods[self.to_uri(cls["module"])]["namespaces"][cls_uri]["metadata"][
                "superClasses"
            ] = []
            for parent in cls["mro"]:
                if parent == cls_name:
                    continue

                if self.classes.get(parent):
                    parent_uri = self.to_uri(self.classes[parent]["module"], parent)
                else:
                    parent_mod = parent.split(".")[0]
                    parent_uri = self.to_external_uri(parent_mod, parent)

                mods[self.to_uri(cls["module"])]["namespaces"][cls_uri]["metadata"][
                    "superClasses"
                ].append(parent_uri)

        return mods

    def create_namespaces_map(self):
        namespaces_maps = [{}, {}]
        for res, hmap in zip(namespaces_maps, [self.internal_mods, self.external_mods]):
            for mod in hmap:
                for namespace in hmap[mod]["methods"]:
                    res[namespace] = mod

        return namespaces_maps

    def get_external_modules(self):
        mods = {}
        for modname, module in self.external_mods.items():
            name = self.to_external_uri(modname).split("/")[2]
            namespaces = module["methods"]

            mods[name] = {"sourceFile": "", "namespaces": {}}

            for namespace, info in namespaces.items():
                # We avoid saving the external module as external method
                if info["name"] != modname:
                    namespace_uri = self.to_external_uri(modname, info["name"])

                    unique = self.get_unique_and_increment()
                    mods[name]["namespaces"][str(unique)] = dict(
                        namespace=namespace_uri, metadata={}
                    )
                    self.namespace_map[namespace_uri] = unique
        return mods

    def get_graph(self):
        graph = {"internalCalls": [], "externalCalls": [], "resolvedCalls": []}

        internal, external = self.create_namespaces_map()

        for src, dst in self.edges:
            uris = []
            for node in [src, dst]:
                if node in internal:
                    mod = internal[node]
                    uri = self.to_uri(mod, node)
                    uris.append(self.namespace_map.get(uri, uri))
                elif node in external:
                    mod = external[node]
                    uris.append(self.namespace_map.get(self.to_external_uri(mod, node)))

            if len(uris) == 2:
                if dst in external:
                    graph["externalCalls"].append([str(uris[0]), str(uris[1]), {}])
                else:
                    graph["internalCalls"].append([str(uris[0]), str(uris[1]), {}])
        return graph

    def generate(self):
        return {
            "product": self.product,
            "forge": self.forge,
            "generator": "PyCG",
            "depset": self.find_dependencies(self.package),
            "version": self.version,
            "timestamp": self.timestamp,
            "modules": {
                "internal": self.get_internal_modules(),
                "external": self.get_external_modules(),
            },
            "graph": self.get_graph(),
            "nodes": self.get_unique_and_increment(),
        }
