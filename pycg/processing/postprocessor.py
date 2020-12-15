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
import ast

from pycg.processing.base import ProcessingBase
from pycg.machinery.definitions import Definition
from pycg import utils

class PostProcessor(ProcessingBase):
    def __init__(self, input_file, modname,
            import_manager, scope_manager, def_manager, class_manager, modules_analyzed=None):
        super().__init__(input_file, modname, modules_analyzed)
        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager
        self.class_manager = class_manager
        self.closured = self.def_manager.transitive_closure()

    def visit_Lambda(self, node):
        counter = self.scope_manager.get_scope(self.current_ns).inc_lambda_counter()
        lambda_name = utils.get_lambda_name(counter)
        super().visit_Lambda(node, lambda_name)

    def visit_Call(self, node):
        self.visit(node.func)

        names = self.retrieve_call_names(node)
        if not names:
            return

        self.last_called_names = names

        for name in names:
            defi = self.def_manager.get(name)
            if not defi:
                continue
            if defi.get_type() == utils.constants.CLS_DEF:
                defi = self.def_manager.get(utils.join_ns(defi.get_ns(), utils.constants.CLS_INIT))
                if not defi:
                    continue
            self.iterate_call_args(defi, node)

    def visit_Assign(self, node):
        self._visit_assign(node.value, node.targets)

    def visit_For(self, node):
        # only handle name targets
        if isinstance(node.target, ast.Name):
            target_def = self.def_manager.get(utils.join_ns(self.current_ns, node.target.id))
            # if the target definition exists
            if target_def:
                iter_decoded = self.decode_node(node.iter)
                # assign the target to the return value
                # of the next function
                for item in iter_decoded:
                    if not isinstance(item, Definition):
                        continue
                    # return value for generators
                    for name in self.closured.get(item.get_ns(), []):
                        # If there exists a next method on the iterable
                        # and if yes, add a pointer to it
                        next_defi = self.def_manager.get(utils.join_ns(name,
                            utils.constants.NEXT_METHOD, utils.constants.RETURN_NAME))
                        if next_defi:
                            for name in self.closured.get(next_defi.get_ns(), []):
                                target_def.get_name_pointer().add(name)
                        else: # otherwise, add a pointer to the name (e.g. a yield)
                            target_def.get_name_pointer().add(name)

        super().visit_For(node)

    def visit_Return(self, node):
        self._visit_return(node)

    def visit_Yield(self, node):
        self._visit_return(node)

    def visit_FunctionDef(self, node):
        # here we iterate decorators
        if node.decorator_list:
            fn_def = self.def_manager.get(utils.join_ns(self.current_ns, node.name))
            reversed_decorators = list(reversed(node.decorator_list))

            # add to the name pointer of the function definition
            # the return value of the first decorator
            # since, now the function is a namespace to that point
            if hasattr(fn_def, "decorator_names") and reversed_decorators:
                last_decoded = self.decode_node(reversed_decorators[-1])
                for d in last_decoded:
                    if not isinstance(d, Definition):
                        continue
                    fn_def.decorator_names.add(utils.join_ns(d.get_ns(), utils.constants.RETURN_NAME))

            previous_names = self.closured.get(fn_def.get_ns(), set())
            for decorator in reversed_decorators:
                # assign the previous_def as the first parameter of the decorator
                decoded = self.decode_node(decorator)
                new_previous_names = set()
                for d in decoded:
                    if not isinstance(d, Definition):
                        continue
                    for name in self.closured.get(d.get_ns(), []):
                        return_ns = utils.join_ns(name, utils.constants.RETURN_NAME)

                        if self.closured.get(return_ns, None) == None:
                            continue

                        new_previous_names = new_previous_names.union(self.closured.get(return_ns))

                        for prev_name in previous_names:
                            pos_arg_names = d.get_name_pointer().get_pos_arg(0)
                            if not pos_arg_names:
                                continue
                            for name in pos_arg_names:
                                arg_def = self.def_manager.get(name)
                                arg_def.get_name_pointer().add(prev_name)
                previous_names = new_previous_names

        super().visit_FunctionDef(node)

    def analyze_submodules(self):
        super().analyze_submodules(PostProcessor, self.import_manager,
                self.scope_manager, self.def_manager, self.class_manager,
                modules_analyzed=self.get_modules_analyzed())

    def analyze(self):
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()
