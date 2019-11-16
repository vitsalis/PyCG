import ast
import os
import sys
import importlib

from pycg.machinery.definitions import DefinitionManager, Definition
from pycg import utils

class PreprocessorVisitor(ast.NodeVisitor):

    def __init__(self, input_file, modname, mod_dir,
            import_manager, scope_manager, def_manager, modules_analyzed=None):
        self.filename = os.path.abspath(input_file)
        self.modname = modname
        self.mod_dir = mod_dir
        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager

        self.name_stack = []

        self.modules_analyzed = set()
        if modules_analyzed:
            self.modules_analyzed = modules_analyzed
        self.modules_analyzed.add(self.modname)

        with open(self.filename, "rt") as f:
            self.contents = f.read()

    @property
    def current_ns(self):
        return ".".join(self.name_stack)

    def _decode_node(self, node):
        if isinstance(node, ast.Name):
            return self.scope_manager.get_def(self.current_ns, node.id)
        elif isinstance(node, ast.Call):
            # TODO: this function shouldn't visit anything
            self.visit(node)
            called_def = self.scope_manager.get_def(self.current_ns, node.func.id)
            # TODO: why is RETURN_NAME on definition manager??
            return_ns = "{}.{}".format(called_def.get_ns(), DefinitionManager.RETURN_NAME)
            return self.def_manager.get(return_ns)
        elif isinstance(node, ast.Lambda):
            lambda_counter = self.scope_manager.get_scope(self.current_ns).get_lambda_counter()
            lambda_name = self._get_lambda_name(lambda_counter)
            return self.scope_manager.get_def(self.current_ns, lambda_name)
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Str):
            return node.s
        else:
            raise Exception("{}: This type is not supported".format(node))

    def _get_fun_defaults(self, node):
        defaults = {}
        start = len(node.args.args) - len(node.args.defaults)
        for cnt, d in enumerate(node.args.defaults, start=start):
            self.visit(d)
            defaults[node.args.args[cnt].arg] = self._decode_node(d)

        start = len(node.args.kwonlyargs) - len(node.args.kw_defaults)
        for cnt, d in enumerate(node.args.kw_defaults, start=start):
            self.visit(d)
            defaults[node.args.kwonlyargs[cnt].arg] = self._decode_node(d)

        return defaults

    def _analyze_submodule(self, fname, modname):
        self.import_manager.set_current_mod(modname)

        visitor = PreprocessorVisitor(fname, modname, self.mod_dir,
            self.import_manager, self.scope_manager, self.def_manager)
        visitor.do_visit()

        self.merge_modules_analyzed(visitor.get_modules_analyzed())

        self.import_manager.set_current_mod(self.modname)

    def _get_lambda_name(self, cnt):
        return "<lambda{}>".format(cnt)

    def get_modules_analyzed(self):
        return self.modules_analyzed

    def merge_modules_analyzed(self, analyzed):
        self.modules_analyzed = self.modules_analyzed.union(analyzed)

    def visit_Module(self, node):
        self.import_manager.set_current_mod(self.modname)
        # initialize module scopes
        functions = self.scope_manager.handle_module(self.modname,
            self.filename, self.contents)

        # create function defs and add them to their scope
        # we do this here, because scope_manager doesn't have an
        # interface with def_manager, and we want function definitions
        # to have the correct points_to set
        for f in functions:
            defi = self.def_manager.get(f)
            if not defi:
                defi = self.def_manager.create(f, Definition.FUN_DEF)

            splitted = f.split(".")
            name = splitted[-1]
            parentns = ".".join(splitted[:-1])
            self.scope_manager.get_scope(parentns).add_def(name, defi)

        defi = self.def_manager.get(self.modname)
        if not defi:
            defi = self.def_manager.create(self.modname, Definition.MOD_DEF)

        self.name_stack.append(self.modname)

        self.generic_visit(node)

        self.name_stack.pop()

    def visit_Import(self, node, prefix='', level=0):
        """
        For imports of the form
            `from something import anything`
        prefix is set to "something".
        For imports of the form
            `from .relative import anything`
        level is set to a number indicating the number
        of parent directories (e.g. in this case level=1)
        """
        def handle_src_name(name):
            # Get the module name and prepend prefix if necessary
            src_name = name
            if prefix:
                src_name = prefix + "." + src_name
            return src_name

        def handle_scopes(tgt_name, modname):
            def create_def(scope, name, imported_def):
                if not name in scope.get_defs():
                    def_ns = "{}.{}".format(scope.get_ns(), name)
                    defi = self.def_manager.get(def_ns)
                    if not defi:
                        defi = self.def_manager.assign(def_ns, imported_def)
                    current_scope.add_def(name, defi)

            current_scope = self.scope_manager.get_scope(self.current_ns)
            imported_scope = self.scope_manager.get_scope(modname)
            if tgt_name == "*":
                for name, defi in imported_scope.get_defs().items():
                    create_def(current_scope, name, defi)
                    current_scope.get_def(name).get_name_pointer().add(defi.get_ns())
            else:
                # if it exists in the imported scope then copy it
                defi = imported_scope.get_def(tgt_name)
                if defi:
                    create_def(current_scope, tgt_name, defi)
                    current_scope.get_def(tgt_name).get_name_pointer().add(imported_scope.get_def(tgt_name).get_ns())

        for import_item in node.names:
            src_name = handle_src_name(import_item.name)
            tgt_name = import_item.asname if import_item.asname else import_item.name
            self.import_manager.handle_import(src_name, level)
            for modname in self.import_manager.get_imports(self.modname):

                # Work on scopes
                fname = self.import_manager.get_filepath(modname)
                # only analyze modules under the current directory
                if self.mod_dir in fname:
                    if not modname in self.modules_analyzed:
                        self._analyze_submodule(fname, modname)
                    handle_scopes(tgt_name, modname)


    def visit_ImportFrom(self, node):
        self.visit_Import(node, prefix=node.module, level=node.level)

    def _handle_function_def(self, node, fn_name):
        defaults = self._get_fun_defaults(node)

        fn_def = self.def_manager.handle_function_def(self.current_ns, fn_name)

        defs_to_create = []
        name_pointer = fn_def.get_name_pointer()
        for pos, arg in enumerate(node.args.args):
            arg_ns = "{}.{}".format(fn_def.get_ns(), arg.arg)
            name_pointer.add_pos_arg(pos, arg.arg, arg_ns)
            defs_to_create.append(arg_ns)

        for arg in node.args.kwonlyargs:
            arg_ns = "{}.{}".format(fn_def.get_ns(), arg.arg)
            # TODO: add_name_arg function
            name_pointer.add_name_arg(arg.arg, arg_ns)
            defs_to_create.append(arg_ns)

        # TODO: Add support for kwargs and varargs
        #if node.args.kwarg:
        #    pass
        #if node.args.vararg:
        #    pass

        for arg_ns in defs_to_create:
            arg_def = self.def_manager.get(arg_ns)
            if not arg_def:
                arg_def = self.def_manager.create(arg_ns, Definition.NAME_DEF)

            self.scope_manager.handle_assign(fn_def.get_ns(), arg_def.get_name(), arg_def)

            # has a default
            arg_name = arg_ns.split(".")[-1]
            if defaults.get(arg_name, None):
                if isinstance(defaults[arg_name], Definition):
                    if defaults[arg_name].is_function_def():
                        arg_def.get_name_pointer().add(defaults[arg_name].get_ns())
                    else:
                        arg_def.merge(defaults[arg_name])
                else:
                    arg_def.get_lit_pointer().add(defaults[arg_name])
        return fn_def

    def visit_FunctionDef(self, node):
        fn_def = self._handle_function_def(node, node.name)

        self.name_stack.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self.name_stack.pop()

    def _handle_assign(self, targetns, decoded):
        defi = self.def_manager.get(targetns)
        if not defi:
            defi = self.def_manager.create(targetns, Definition.NAME_DEF)

        if isinstance(decoded, Definition):
            defi.get_name_pointer().add(decoded.get_ns())
        else:
            defi.get_lit_pointer().add(decoded)
        return defi

    def visit_Assign(self, node):
        self.visit(node.value)

        decoded = self._decode_node(node.value)
        for target in node.targets:
            targetns = "{}.{}".format(self.current_ns, target.id)
            defi = self._handle_assign(targetns, decoded)
            self.scope_manager.handle_assign(self.current_ns, target.id, defi)

    def visit_Return(self, node):
        self.visit(node.value)

        return_ns = "{}.{}".format(self.current_ns, DefinitionManager.RETURN_NAME)
        self._handle_assign(return_ns, self._decode_node(node.value))

    def visit_Call(self, node):
        fullns = "{}.{}".format(self.current_ns, node.func.id)
        defi = self.scope_manager.get_def(self.current_ns, node.func.id)
        if not defi:
            defi = self.def_manager.create(fullns, Definition.FUN_DEF)

        for pos, arg in enumerate(node.args):
            decoded = self._decode_node(arg)
            if defi.is_function_def():
                pos_arg_names = defi.get_name_pointer().get_pos_arg(pos)
                # if arguments for this position exist update their namespace
                for name in pos_arg_names:
                    arg_def = self.def_manager.get(name)
                    if isinstance(decoded, Definition):
                        arg_def.get_name_pointer().add(decoded.get_ns())
                    else:
                        arg_def.get_lit_pointer().add(decoded)
            else:
                if isinstance(decoded, Definition):
                    defi.get_name_pointer().add_pos_arg(pos, None, decoded.get_ns())
                else:
                    defi.get_name_pointer().add_pos_lit_arg(pos, None, decoded)

        for keyword in node.keywords:
            decoded = self._decode_node(keyword.value)
            if defi.is_function_def():
                arg_names = defi.get_name_pointer().get_arg(keyword.arg)
                for name in arg_names:
                    arg_def = self.def_manager.get(name)
                    if isinstance(decoded, Definition):
                        arg_def.get_name_pointer().add(decoded.get_ns())
                    else:
                        arg_def.get_lit_pointer().add(decoded)
            else:
                if isinstance(decoded, Definition):
                    defi.get_name_pointer().add_arg(keyword.arg, decoded.get_ns())
                else:
                    defi.get_name_pointer().add_lit_arg(keyword.arg, decoded)

        self.visit(node.func)

    def visit_Lambda(self, node):
        # The name of a lambda is defined by the counter of the current scope
        current_scope = self.scope_manager.get_scope(self.current_ns)
        lambda_counter = current_scope.inc_lambda_counter()
        lambda_name = self._get_lambda_name(lambda_counter)
        lambda_full_ns = "{}.{}".format(self.current_ns, lambda_name)

        # create a scope for the lambda
        self.scope_manager.create_scope(lambda_full_ns, current_scope)
        lambda_def = self._handle_function_def(node, lambda_name)
        # add it to the current scope
        current_scope.add_def(lambda_name, lambda_def)

        self.name_stack.append(lambda_name)
        self.visit(node.body)
        self.name_stack.pop()

    def do_visit(self):
        self.visit(ast.parse(self.contents, self.filename))

class Preprocessor(object):
    def __init__(self, input_file, import_manager, scope_manager, def_manager):
        self.input_file = os.path.abspath(input_file)

        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager

        splitted = self.input_file.split("/")
        self.mod = utils.to_mod_name(splitted[-1])
        self.mod_dir = "/".join(splitted[:-1])

    def analyze(self):
        # add root node
        self.import_manager.create_node(self.mod)
        self.import_manager.set_filepath(self.mod, self.input_file)
        self.import_manager.set_current_mod(self.mod)

        visitor = PreprocessorVisitor(self.input_file, self.mod, self.mod_dir,
            self.import_manager, self.scope_manager, self.def_manager)
        visitor.do_visit()

    def cleanup(self):
        self.import_manager.remove_hooks()
