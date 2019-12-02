import ast
import os
import importlib

from pycg.machinery.definitions import DefinitionManager, Definition
from pycg import utils
from pycg.processing.base import ProcessingBase

class PreProcessorVisitor(ProcessingBase):
    def __init__(self, input_file, modname, mod_dir,
            import_manager, scope_manager, def_manager, class_manager,
            modules_analyzed=None):
        super().__init__(input_file, modname, modules_analyzed)

        self.modname = modname
        self.mod_dir = mod_dir
        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager
        self.class_manager = class_manager

    def _get_fun_defaults(self, node):
        defaults = {}
        start = len(node.args.args) - len(node.args.defaults)
        for cnt, d in enumerate(node.args.defaults, start=start):
            self.visit(d)
            defaults[node.args.args[cnt].arg] = self.decode_node(d)

        start = len(node.args.kwonlyargs) - len(node.args.kw_defaults)
        for cnt, d in enumerate(node.args.kw_defaults, start=start):
            self.visit(d)
            defaults[node.args.kwonlyargs[cnt].arg] = self.decode_node(d)

        return defaults

    def analyze_submodule(self, modname):
        super().analyze_submodule(PreProcessorVisitor, modname, self.mod_dir,
            self.import_manager, self.scope_manager, self.def_manager, self.class_manager)

    def visit_Module(self, node):
        def iterate_mod_items(items, const):
            for item in items:
                defi = self.def_manager.get(item)
                if not defi:
                    defi = self.def_manager.create(item, const)

                splitted = item.split(".")
                name = splitted[-1]
                parentns = ".".join(splitted[:-1])
                self.scope_manager.get_scope(parentns).add_def(name, defi)

        self.import_manager.set_current_mod(self.modname)
        # initialize module scopes
        items = self.scope_manager.handle_module(self.modname,
            self.filename, self.contents)

        # create function and class defs and add them to their scope
        # we do this here, because scope_manager doesn't have an
        # interface with def_manager, and we want function definitions
        # to have the correct points_to set
        iterate_mod_items(items["functions"], utils.constants.FUN_DEF)
        iterate_mod_items(items["classes"], utils.constants.CLS_DEF)

        defi = self.def_manager.get(self.modname)
        if not defi:
            defi = self.def_manager.create(self.modname, utils.constants.MOD_DEF)

        super().visit_Module(node)

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
                    def_ns = utils.join_ns(scope.get_ns(), name)
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
                    self.analyze_submodule(modname)
                    handle_scopes(tgt_name, modname)


    def visit_ImportFrom(self, node):
        self.visit_Import(node, prefix=node.module, level=node.level)

    def _handle_function_def(self, node, fn_name):
        defaults = self._get_fun_defaults(node)

        fn_def = self.def_manager.handle_function_def(self.current_ns, fn_name)

        defs_to_create = []
        name_pointer = fn_def.get_name_pointer()
        for pos, arg in enumerate(node.args.args):
            arg_ns = utils.join_ns(fn_def.get_ns(), arg.arg)
            name_pointer.add_pos_arg(pos, arg.arg, arg_ns)
            defs_to_create.append(arg_ns)

        for arg in node.args.kwonlyargs:
            arg_ns = utils.join_ns(fn_def.get_ns(), arg.arg)
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
                arg_def = self.def_manager.create(arg_ns, utils.constants.NAME_DEF)

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

        super().visit_FunctionDef(node)

    def _handle_assign(self, targetns, decoded):
        defi = self.def_manager.get(targetns)
        if not defi:
            defi = self.def_manager.create(targetns, utils.constants.NAME_DEF)

        if isinstance(decoded, Definition):
            defi.get_name_pointer().add(decoded.get_ns())
        else:
            defi.get_lit_pointer().add(decoded)
        return defi

    def visit_Tuple(self, node):
        # node.ctx == ast.Load means get
        # node.ctx == ast.Store means set
        for elt in node.elts:
            self.visit(elt)

    def visit_Assign(self, node):
        self.visit(node.value)

        decoded = self.decode_node(node.value)

        def do_assign(decoded, target):
            self.visit(target)
            if isinstance(target, ast.Tuple):
                for pos, elt in enumerate(target.elts):
                    do_assign(decoded[pos], elt)
            else:
                targetns = utils.join_ns(self.current_ns, target.id)
                defi = self._handle_assign(targetns, decoded)
                self.scope_manager.handle_assign(self.current_ns, target.id, defi)

        for target in node.targets:
            do_assign(decoded, target)


    def visit_Return(self, node):
        self.visit(node.value)

        return_ns = utils.join_ns(self.current_ns, utils.constants.RETURN_NAME)
        self._handle_assign(return_ns, self.decode_node(node.value))

    def visit_Call(self, node):
        self.visit(node.func)
        # if it is not a name there's nothing we can do here
        # ModuleVisitor will be able to resolve those calls
        # since it'll have the name tracking information
        if not isinstance(node.func, ast.Name):
            return

        fullns = utils.join_ns(self.current_ns, node.func.id)

        defi = self.scope_manager.get_def(self.current_ns, node.func.id)
        if not defi:
            return

        self.iterate_call_args(defi, node)

    def visit_Lambda(self, node):
        # The name of a lambda is defined by the counter of the current scope
        current_scope = self.scope_manager.get_scope(self.current_ns)
        lambda_counter = current_scope.inc_lambda_counter()
        lambda_name = utils.get_lambda_name(lambda_counter)
        lambda_full_ns = utils.join_ns(self.current_ns, lambda_name)

        # create a scope for the lambda
        self.scope_manager.create_scope(lambda_full_ns, current_scope)
        lambda_def = self._handle_function_def(node, lambda_name)
        # add it to the current scope
        current_scope.add_def(lambda_name, lambda_def)

        super().visit_Lambda(node, lambda_name)

    def visit_ClassDef(self, node):
        # create a definition for the class (node.name)
        cls_def = self.def_manager.handle_class_def(self.current_ns, node.name)

        # iterate bases to compute MRO for the class
        cls = self.class_manager.get(cls_def.get_ns())
        if not cls:
            cls = self.class_manager.create(cls_def.get_ns())
        for base in node.bases:
            # all bases are of the type ast.Name
            if base.id == utils.constants.OBJECT_BASE:
                continue
            self.visit(base)
            base_def = self.scope_manager.get_def(self.current_ns, base.id)
            if not base_def:
                continue
            # add the base as a parent
            cls.add_parent(base_def.get_ns())

            # add the base's parents
            parent_cls = self.class_manager.get(base_def.get_ns())
            cls.add_parent(parent_cls.get_mro())

        cls.compute_mro()

        super().visit_ClassDef(node)

    def analyze(self):
        self.visit(ast.parse(self.contents, self.filename))

class PreProcessor(object):
    def __init__(self, input_file, import_manager, scope_manager, def_manager, class_manager):
        self.input_file = os.path.abspath(input_file)

        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager
        self.class_manager = class_manager

        splitted = self.input_file.split("/")
        self.mod = utils.to_mod_name(splitted[-1])
        self.mod_dir = "/".join(splitted[:-1])

    def analyze(self):
        # add root node
        self.import_manager.create_node(self.mod)
        self.import_manager.set_filepath(self.mod, self.input_file)
        self.import_manager.set_current_mod(self.mod)

        visitor = PreProcessorVisitor(self.input_file, self.mod, self.mod_dir,
            self.import_manager, self.scope_manager, self.def_manager, self.class_manager)
        visitor.analyze()

    def cleanup(self):
        self.import_manager.remove_hooks()
