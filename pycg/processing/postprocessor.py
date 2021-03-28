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
    def __init__(self, input_file, modname, import_manager,
            scope_manager, def_manager, class_manager, module_manager, modules_analyzed=None):
        super().__init__(input_file, modname, modules_analyzed)
        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager
        self.class_manager = class_manager
        self.module_manager = module_manager
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
                self.update_parent_classes(defi)
                defi = self.def_manager.get(utils.join_ns(defi.get_ns(), utils.constants.CLS_INIT))
                if not defi:
                    continue
            self.iterate_call_args(defi, node)

    def visit_Assign(self, node):
        self._visit_assign(node.value, node.targets)

    def visit_Return(self, node):
        self._visit_return(node)

    def visit_Yield(self, node):
        self._visit_return(node)

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

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

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

    def visit_ClassDef(self, node):
        # create a definition for the class (node.name)
        cls_def = self.def_manager.handle_class_def(self.current_ns, node.name)

        # iterate bases to compute MRO for the class
        cls = self.class_manager.get(cls_def.get_ns())
        if not cls:
            cls = self.class_manager.create(cls_def.get_ns(), self.modname)

        cls.clear_mro()
        for base in node.bases:
            # all bases are of the type ast.Name
            self.visit(base)

            bases = self.decode_node(base)
            for base_def in bases:
                if not isinstance(base_def, Definition):
                    continue
                names = set()
                if base_def.get_name_pointer().get():
                    names = base_def.get_name_pointer().get()
                else:
                    names.add(base_def.get_ns())
                for name in names:
                    # add the base as a parent
                    cls.add_parent(name)

                    # add the base's parents
                    parent_cls = self.class_manager.get(name)
                    if parent_cls:
                        cls.add_parent(parent_cls.get_mro())

        cls.compute_mro()

        super().visit_ClassDef(node)

    def visit_List(self, node):
        # Works similarly with dicts
        current_scope = self.scope_manager.get_scope(self.current_ns)
        list_counter = current_scope.inc_list_counter()
        list_name = utils.get_list_name(list_counter)
        list_full_ns = utils.join_ns(self.current_ns, list_name)

        # create a scope for the list
        list_scope = self.scope_manager.create_scope(list_full_ns, current_scope)

        # create a list definition
        list_def = self.def_manager.get(list_full_ns)
        if not list_def:
            list_def = self.def_manager.create(list_full_ns, utils.constants.NAME_DEF)
        current_scope.add_def(list_name, list_def)

        self.name_stack.append(list_name)
        for idx, elt in enumerate(node.elts):
            self.visit(elt)
            key_full_ns = utils.join_ns(list_def.get_ns(), utils.get_int_name(idx))
            key_def = self.def_manager.get(key_full_ns)
            if not key_def:
                key_def = self.def_manager.create(key_full_ns, utils.constants.NAME_DEF)

            decoded_elt = self.decode_node(elt)
            for v in decoded_elt:
                if isinstance(v, Definition):
                    key_def.get_name_pointer().add(v.get_ns())
                else:
                    key_def.get_lit_pointer().add(v)

        self.name_stack.pop()

    def visit_Dict(self, node):
        # 1. create a scope using a counter
        # 2. Iterate keys and add them as children of the scope
        # 3. Iterate values and makes a points to connection with the keys
        current_scope = self.scope_manager.get_scope(self.current_ns)
        dict_counter = current_scope.inc_dict_counter()
        dict_name = utils.get_dict_name(dict_counter)
        dict_full_ns = utils.join_ns(self.current_ns, dict_name)

        # create a scope for the dict
        dict_scope = self.scope_manager.create_scope(dict_full_ns, current_scope)

        # Create a dict definition
        dict_def = self.def_manager.get(dict_full_ns)
        if not dict_def:
            dict_def = self.def_manager.create(dict_full_ns, utils.constants.NAME_DEF)
        # add it to the current scope
        current_scope.add_def(dict_name, dict_def)

        self.name_stack.append(dict_name)
        for key, value in zip(node.keys, node.values):
            if key:
                self.visit(key)
            if value:
                self.visit(value)
            decoded_key = self.decode_node(key)
            decoded_value = self.decode_node(value)

            # iterate decoded keys and values
            # to do the assignment operation
            for k in decoded_key:
                if isinstance(k, Definition):
                    # get literal pointer
                    names = k.get_lit_pointer().get()
                else:
                    names = set()
                    if isinstance(k, list):
                        continue
                    names.add(k)
                for name in names:
                    # create a definition for the key
                    if isinstance(name, int):
                        name = utils.get_int_name(name)
                    key_full_ns = utils.join_ns(dict_def.get_ns(), str(name))
                    key_def = self.def_manager.get(key_full_ns)
                    if not key_def:
                        key_def = self.def_manager.create(key_full_ns, utils.constants.NAME_DEF)
                    dict_scope.add_def(str(name), key_def)
                    for v in decoded_value:
                        if isinstance(v, Definition):
                            key_def.get_name_pointer().add(v.get_ns())
                        else:
                            key_def.get_lit_pointer().add(v)
        self.name_stack.pop()

    def update_parent_classes(self, defi):
        cls = self.class_manager.get(defi.get_ns())
        if not cls:
            return
        current_scope = self.scope_manager.get_scope(defi.get_ns())
        for parent in cls.get_mro():
            parent_def = self.def_manager.get(parent)
            if not parent_def:
                continue
            parent_scope = self.scope_manager.get_scope(parent)
            if not parent_scope:
                continue
            parent_items = list(parent_scope.get_defs().keys())
            for key, child_def in current_scope.get_defs().items():
                if key == "__init__":
                    continue
                # resolve name from the parent_def
                names = self.find_cls_fun_ns(parent_def.get_ns(), key)

                new_ns = utils.join_ns(parent_def.get_ns(), key)
                new_def = self.def_manager.get(new_ns)
                if not new_def:
                    new_def = self.def_manager.create(new_ns, utils.constants.NAME_DEF)

                new_def.get_name_pointer().add_set(names)
                new_def.get_name_pointer().add(child_def.get_ns())

    def analyze_submodules(self):
        super().analyze_submodules(PostProcessor, self.import_manager,
                self.scope_manager, self.def_manager, self.class_manager,
                self.module_manager, modules_analyzed=self.get_modules_analyzed())

    def analyze(self):
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()
