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
        if not modules_analyzed:
            self.modules_analyzed = set()
        else:
            self.modules_analyzed = modules_analyzed
        self.modules_analyzed.add(self.modname)
        with open(self.filename, "rt") as f:
            self.contents = f.read()


    def _get_current_namespace(self):
        return ".".join(self.name_stack)

    def _analyze_submodule(self, fname, modname):
        self.import_manager.set_current_mod(modname)

        visitor = PreprocessorVisitor(fname, modname, self.mod_dir,
            self.import_manager, self.scope_manager, self.def_manager)
        visitor.do_visit()

        self.merge_modules_analyzed(visitor.get_modules_analyzed())

        self.import_manager.set_current_mod(self.modname)

    def _get_value_from_node(self, node):
        # TODO add more types
        current_ns = self._get_current_namespace()
        if isinstance(node, ast.Name):
            defi = self.scope_manager.get_def(current_ns, node.id)
            return {"value": defi,
                    "type": DefinitionManager.NAME_TYPE}

        elif isinstance(node, ast.Call):
            self.visit(node)
            defi = self.scope_manager.get_def(current_ns, node.func.id)
            return_ns = "{}.{}".format(defi.get_ns(), DefinitionManager.RETURN_NAME)
            return_def = self.def_manager.get(return_ns)
            return {"value": return_def, "type": DefinitionManager.NAME_TYPE}
        elif isinstance(node, ast.Num):
            return {"value": node.n, "type": DefinitionManager.LIT_TYPE}
        elif isinstance(node, ast.Str):
            return {"value": node.s, "type": DefinitionManager.LIT_TYPE}
        else:
            raise Exception("{} not supported".format(node))

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

        mod_pointer = defi.get_mod_pointer()
        mod_pointer.add(self.modname)

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

            current_scope = self.scope_manager.get_scope(self._get_current_namespace())
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

    def visit_FunctionDef(self, node):
        # only last n arguements have defaults
        defaults = {}
        start = len(node.args.args) - len(node.args.defaults)
        for cnt, d in enumerate(node.args.defaults, start=start):
            self.visit(d)
            defaults[cnt] = self._get_value_from_node(d)


        self.def_manager.handle_function_def(self._get_current_namespace(),
            node.name, [arg.arg for arg in node.args.args], defaults)

        fn_ns = "{}.{}".format(self._get_current_namespace(), node.name)

        defs = self.def_manager.get_arg_defs(fn_ns)

        self.scope_manager.add_scope_defs(fn_ns, defs)

        self.name_stack.append(node.name)

        # TODO: Add for kwargs
        #for a in node.args.kwonlyargs:
        #    pass

        # TODO
        #for d in node.args.kw_defaults:
        #    self.visit(d)

        for stmt in node.body:
            self.visit(stmt)

        self.name_stack.pop()

    def visit_Assign(self, node):
        value = self._get_value_from_node(node.value)
        fullns = self._get_current_namespace()
        for target in node.targets:
            targetns = "{}.{}".format(fullns, target.id)
            defi = self.def_manager.handle_assign(targetns, value)
            self.scope_manager.handle_assign(fullns, target.id, defi)

    def visit_Name(self, node):
        pass

    def visit_Return(self, node):
        fullns = self._get_current_namespace()
        return_ns = "{}.{}".format(fullns, DefinitionManager.RETURN_NAME)

        value = self._get_value_from_node(node.value)
        defi = self.def_manager.handle_assign(return_ns, value)

    def visit_Call(self, node):
        args = {}
        for cnt, arg in enumerate(node.args):
            args[cnt] = self._get_value_from_node(arg)

        current_ns = self._get_current_namespace()
        defi = self.scope_manager.get_def(current_ns, node.func.id)
        if not defi:
            fullns = "{}.{}".format(current_ns, node.func.id)
            defi = self.def_manager.create(fullns, Definition.FUN_DEF)
        self.def_manager.update_def_args(defi, args)

        self.visit(node.func)

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
