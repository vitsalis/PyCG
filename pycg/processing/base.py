import ast
import os

from pycg import utils
from pycg.machinery.definitions import Definition

class ProcessingBase(ast.NodeVisitor):
    def __init__(self, filename, modname, modules_analyzed=None):
        self.modname = modname

        self.modules_analyzed = set()
        if modules_analyzed:
            self.modules_analyzed = modules_analyzed
        self.modules_analyzed.add(self.modname)

        self.filename = os.path.abspath(filename)

        with open(filename, "rt") as f:
            self.contents = f.read()

        self.name_stack = []
        self.last_called_names = None

    def get_modules_analyzed(self):
        return self.modules_analyzed

    def merge_modules_analyzed(self, analyzed):
        self.modules_analyzed = self.modules_analyzed.union(analyzed)

    @property
    def current_ns(self):
        return ".".join(self.name_stack)

    def visit_Module(self, node):
        self.name_stack.append(self.modname)
        self.scope_manager.get_scope(self.modname).reset_counters()
        self.generic_visit(node)
        self.name_stack.pop()

    def visit_FunctionDef(self, node):
        self.name_stack.append(node.name)
        self.scope_manager.get_scope(self.current_ns).reset_counters()
        for stmt in node.body:
            self.visit(stmt)
        self.name_stack.pop()

    def visit_Lambda(self, node, lambda_name=None):
        self.name_stack.append(lambda_name)
        self.visit(node.body)
        self.name_stack.pop()

    def visit_BinOp(self, node):
        self.visit(node.left)
        self.visit(node.right)

    def visit_ClassDef(self, node):
        self.name_stack.append(node.name)
        self.scope_manager.get_scope(self.current_ns).reset_counters()
        for stmt in node.body:
            self.visit(stmt)
        self.name_stack.pop()

    def decode_node(self, node):
        if isinstance(node, ast.Name):
            return self.scope_manager.get_def(self.current_ns, node.id)
        elif isinstance(node, ast.Call):
            called_def = self.scope_manager.get_def(self.current_ns, node.func.id)
            return_ns = utils.constants.INVALID_NAME
            if called_def.get_type() == utils.constants.FUN_DEF:
                return_ns = utils.join_ns(called_def.get_ns(), utils.constants.RETURN_NAME)
            elif called_def.get_type() == utils.constants.CLS_DEF:
                return_ns = called_def.get_ns()
            return self.def_manager.get(return_ns)
        elif isinstance(node, ast.Lambda):
            lambda_counter = self.scope_manager.get_scope(self.current_ns).get_lambda_counter()
            lambda_name = utils.get_lambda_name(lambda_counter)
            return self.scope_manager.get_def(self.current_ns, lambda_name)
        elif isinstance(node, ast.Tuple):
            decoded = []
            for elt in node.elts:
                decoded.append(self.decode_node(elt))
            return decoded
        elif isinstance(node, ast.BinOp):
            decoded_left = self.decode_node(node.left)
            decoded_right = self.decode_node(node.right)
            # return the non definition types if we're talking about a binop
            # since we only care about the type of the return (num, str, etc)
            if not isinstance(decoded_left, Definition):
                return decoded_left
            if not isinstance(decoded_right, Definition):
                return decoded_right
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Str):
            return node.s
        else:
            raise Exception("{}: This type is not supported".format(node))

    def iterate_call_args(self, defi, node):
        for pos, arg in enumerate(node.args):
            self.visit(arg)
            decoded = self.decode_node(arg)
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
            self.visit(keyword.value)
            decoded = self.decode_node(keyword.value)
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

    def retrieve_call_names(self, node):
        names = set()
        if isinstance(node.func, ast.Name):
            defi = self.scope_manager.get_def(self.current_ns, node.func.id)
            names = self.closured.get(defi.get_ns(), None)
        elif isinstance(node.func, ast.Call):
            for name in self.last_called_names:
                return_ns = utils.join_ns(name, utils.constants.RETURN_NAME)
                returns = self.closured.get(return_ns)
                if not returns:
                    continue
                for ret in returns:
                    defi = self.def_manager.get(ret)
                    names.add(defi.get_ns())
        elif isinstance(node.func, ast.Attribute):
            parent = self.decode_node(node.func.value)
            closured = self.closured.get(parent.get_ns())
            for name in closured:
                defi = self.def_manager.get(name)
                if not defi:
                    continue
                if defi.get_type() == utils.constants.CLS_DEF:
                    names.add(self.find_cls_fun_ns(defi.get_ns(), node.func.attr))
                if defi.get_type() == utils.constants.FUN_DEF:
                    names.add(utils.join_ns(name, node.func.attr))

        return names

    def analyze_submodules(self, cls, *args, **kwargs):
        imports = self.import_manager.get_imports(self.modname)

        for imp in imports:
            self.analyze_submodule(cls, imp, *args, **kwargs)

    def analyze_submodule(self, cls, imp, *args, **kwargs):
        if imp in self.get_modules_analyzed():
            return

        fname = self.import_manager.get_filepath(imp)

        self.import_manager.set_current_mod(imp)

        visitor = cls(fname, imp, *args, **kwargs)
        visitor.analyze()
        self.merge_modules_analyzed(visitor.get_modules_analyzed())

        self.import_manager.set_current_mod(self.modname)

    def find_cls_fun_ns(self, cls_name, fn):
        cls = self.class_manager.get(cls_name)
        if not cls:
            return

        for item in cls.get_mro():
            ns = utils.join_ns(item, fn)
            if self.def_manager.get(ns):
                return ns
