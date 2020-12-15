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
from pycg import utils

class ScopeManager(object):
    """Manages the scope entries"""

    def __init__(self):
        self.scopes = {}

    def handle_module(self, modulename, filename, contents):
        functions = []
        classes = []
        def process(namespace, parent, table):
            name = table.get_name() if table.get_name() != 'top' else ''
            if name:
                fullns = utils.join_ns(namespace, name)
            else:
                fullns = namespace

            if table.get_type() == "function":
                functions.append(fullns)

            if table.get_type() == "class":
                classes.append(fullns)

            sc = self.create_scope(fullns, parent)

            for t in table.get_children():
                process(fullns, sc, t)

        process(modulename, None, symtable.symtable(contents, filename, compile_type="exec"))
        return {"functions": functions, "classes": classes}

    def handle_assign(self, ns, target, defi):
        scope = self.get_scope(ns)
        if scope:
            scope.add_def(target, defi)

    def get_def(self, current_ns, var_name):
        current_scope = self.get_scope(current_ns)
        while current_scope:
            defi = current_scope.get_def(var_name)
            if defi:
                return defi
            current_scope = current_scope.parent

    def get_scope(self, namespace):
        if namespace in self.get_scopes():
            return self.get_scopes()[namespace]

    def create_scope(self, namespace, parent):
        if not namespace in self.scopes:
            sc = ScopeItem(namespace, parent)
            self.scopes[namespace] = sc
        return self.scopes[namespace]

    def get_scopes(self):
        return self.scopes

class ScopeItem(object):
    def __init__(self, fullns, parent):
        if parent and not isinstance(parent, ScopeItem):
            raise ScopeError("Parent must be a ScopeItem instance")

        if not isinstance(fullns, str):
            raise ScopeError("Namespace should be a string")

        self.parent = parent
        self.defs = {}
        self.lambda_counter = 0
        self.dict_counter = 0
        self.list_counter = 0
        self.fullns = fullns

    def get_ns(self):
        return self.fullns

    def get_defs(self):
        return self.defs

    def get_def(self, name):
        defs = self.get_defs()
        if name in defs:
            return defs[name]

    def get_lambda_counter(self):
        return self.lambda_counter

    def get_dict_counter(self):
        return self.dict_counter

    def get_list_counter(self):
        return self.list_counter

    def inc_lambda_counter(self, val=1):
        self.lambda_counter += val
        return self.lambda_counter

    def inc_dict_counter(self, val=1):
        self.dict_counter += val
        return self.dict_counter

    def inc_list_counter(self, val=1):
        self.list_counter += val
        return self.list_counter

    def reset_counters(self):
        self.lambda_counter = 0
        self.dict_counter = 0
        self.list_counter = 0

    def add_def(self, name, defi):
        self.defs[name] = defi

    def merge_def(self, name, to_merge):
        if not name in self.defs:
            self.defs[name] = to_merge
            return

        self.defs[name].merge_points_to(to_merge.get_points_to())

class ScopeError(Exception):
    pass
