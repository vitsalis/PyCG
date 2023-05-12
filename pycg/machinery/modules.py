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
class ModuleManager:
    def __init__(self):
        self.internal = {}
        self.external = {}

    def create(self, name, fname, external=False):
        mod = Module(name, fname)
        if external:
            self.external[name] = mod
        else:
            self.internal[name] = mod
        return mod

    def get(self, name):
        if name in self.internal:
            return self.internal[name]
        if name in self.external:
            return self.external[name]

    def get_internal_modules(self):
        return self.internal

    def get_external_modules(self):
        return self.external


class Module:
    def __init__(self, name, filename):
        self.name = name
        self.filename = filename
        self.methods = dict()

    def get_name(self):
        return self.name

    def get_filename(self):
        return self.filename

    def get_methods(self):
        return self.methods

    def add_method(self, method, first=None, last=None):
        if not self.methods.get(method, None):
            self.methods[method] = dict(name=method, first=first, last=last)
