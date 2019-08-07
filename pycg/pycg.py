import sys
import os
import ast

from pycg.representations import Node, Scope, CallGraph

from pycg.utils import analyze_scopes, discover_locals, to_mod_name, parent_ns, log, transitive_closure

class Visitor(ast.NodeVisitor):
    def __init__(self, modulename, filename, modules_analyzed=[]):
        self.filename = filename
        self.parent_dir = os.path.dirname(filename)
        self.modulename = modulename
        with open(filename, "rt") as f:
            self.contents = f.read()

        self.pass_no = 0
        self.local_modules = discover_locals(self.parent_dir)
        self.scopes = analyze_scopes(self.modulename, self.contents, self.filename)
        self.modules_analyzed = list((set(modules_analyzed + [modulename])))
        self.cg = CallGraph()
        self.functions = []
        self.tracking = {}
        self.name_stack = []
        self.scope_stack = []
        self.submodules = []

    def merge_tracking(self, tracking):
        for n in tracking:
            if n not in self.tracking:
                self.tracking[n] = tracking[n]

    def add_tracking(self, name, target, follow=False):
        if name not in self.tracking:
            self.tracking[name] = []
        if follow and target in self.tracking:
            self.tracking[name] = list(set(self.tracking[name] + self.tracking[target]))
        else:
            if target not in self.tracking[name]:
                self.tracking[name].append(target)

    def get_current_namespace(self):
        # The name stack contains each name contained in the path
        # to the current line of code being analyzed
        # Join the names and get the current namespace
        return ".".join(self.name_stack)

    def output_call_graph(self):
        return self.cg.output()

    def merge_scopes(self, scopes):
        """
        Gets the scopes of a different module
        and merges them with the current scopes.
        We do this in order to get proper
        `returns_to` sets for external functions called
        """
        for s in scopes:
            if s not in self.scopes:
                self.scopes[s] = scopes[s]

    def get_scopes(self):
        # TODO: give them in a different format???
        return self.scopes

    def merge_analyzed_for(self, modname, analyzed):
        self.modules_analyzed = list(set(self.modules_analyzed + analyzed))

    def find_type(self, name):
        # Gets a function name and visits the scope stack in a reverse order
        # Looking for a function definition matching the name
        for ns, scope in reversed(self.scope_stack):
            if name in scope.defs:
                if scope.defs[name]["type"] != Scope.UNKNOWN:
                    return scope.defs[name]["type"]

        return Scope.UNKNOWN

    def find_ns(self, name):
        # Gets a function name and visits the scope stack in a reverse order
        # Looking for a function definition matching the name
        for ns, scope in reversed(self.scope_stack):
            if name in scope.defs:
                if scope.defs[name]["type"] == Scope.IMPORT_DEF:
                    # TODO: maybe points of a function def has more than one elem?
                    return list(scope.defs[name]["points"])[0]
                if scope.defs[name]["type"] != Scope.UNKNOWN:
                    return "%s.%s" % (ns, name)

    def find_points_to(self, name):
        # Gets a function name and visits the scope stack in a reverse order
        # Looking for a function definition matching the name
        for ns, scope in reversed(self.scope_stack):
            if name in scope.defs:
                if len(scope.defs[name]["points"]):
                    return scope.defs[name]["points"]
        return set()

    def find_def_type(self, name):
        # Gets a function name and visits the scope stack in a reverse order
        # Looking for a function definition matching the name
        for ns, scope in reversed(self.scope_stack):
            if name in scope.defs:
                return scope.defs[name]["type"]


    def visit_Module(self, node):
        # Add modulename ans its scope to the stack
        self.name_stack.append(self.modulename)
        self.scope_stack.append((self.modulename, self.scopes[self.modulename]))

        self.generic_visit(node)

        # Revert stack
        self.scope_stack.pop()
        self.name_stack.pop()

    def visit_Import(self, node, prefix='', level=0):
        """
        Parse a "from <prefix> import <node.name> as <asname>" statement
        For each import item:
            1) Get the scope of the parent and add a reference to
                the imported module under import_defs dictionary
            2) Check if the imported module appears under the same
                directory as the current module (meaning it is a local)
            3) If yes, analyze the imported module and merge its call graph
                with the call graph of the current module
        """

        # Retrieve filename of imported module if it is a local module
        def retrieve_local(name):
            if not name:
                return None, None

            if name in self.local_modules:
                return (name, self.local_modules[name])
            splitted = name.split(".")
            return retrieve_local(".".join(splitted[:-1]))

        def add_mod(module, filename, tgt_name, points_to):
            if (module, filename) not in self.submodules:
                self.submodules.append((module, filename))

            # handle * imports
            if tgt_name == "*":
                if self.scopes.get(module, None):
                    for tgt in self.scopes[module].defs:
                        stack_head.add_def(tgt, Scope.IMPORT_DEF, "%s.%s" % (module, tgt))
            else:
                stack_head.add_def(tgt_name, Scope.IMPORT_DEF, points_to)

        def find_and_add_init(modname, filename, tgt_name, points_to):
            init_mod = ".".join(modname.split(".")[:-1]) + "." + "__init__"
            if init_mod.startswith("."):
                init_mod = init_mod[1:]

            init_path = os.path.join("/".join(filename.split("/")[:-1]), "__init__.py")
            if os.path.exists(init_path):
                add_mod(init_mod, init_path, tgt_name, points_to)

        for import_item in node.names:
            # Retrieve actual name and asname
            src_name = import_item.name
            tgt_name = import_item.asname if import_item.asname is not None else src_name

            # prefix is the <from_name>
            points_to = prefix + "." + src_name if prefix else src_name

            # Modify the current scope to contain the imported module
            stack_head = self.scope_stack[-1][1]


            # only the last part of the import is kept in the namespace
            tgt_name = tgt_name.split(".")[-1]
            module, filename = retrieve_local(points_to)
            if module and filename:
                # level is for relative imports
                if level > 0:
                    modname = self.modulename
                    while level > 0:
                        modname = parent_ns(modname)
                        level -= 1
                    if modname:
                        points_to = modname + "." + points_to
                        module = modname + "." + module

                add_mod(module, filename, tgt_name, points_to)
                find_and_add_init(module, filename, tgt_name, points_to)
            else:
                # It is a third party module, just add a node for it
                self.cg.add_node(points_to)

    def visit_ImportFrom(self, node):
        # Same process as import but with a prefix
        self.visit_Import(node, prefix=node.module, level=node.level)

    def visit_FunctionDef(self, node):
        current_ns = self.get_current_namespace()

        # Function Definition: Create a new node in the graph
        node_name = "%s.%s" % (current_ns, node.name)
        self.cg.add_node(node_name)
        self.functions.append(node_name)


        # Will visit statements of function defined
        # Add function name to the name stack
        self.name_stack.append(node.name)
        # Add the namespace inside the function and its scope into the stack
        new_ns = self.get_current_namespace()
        self.scope_stack.append((new_ns, self.scopes[new_ns]))

        for cnt, a in enumerate(node.args.args):
            self.scopes[new_ns].defs[a.arg]["type"] = Scope.ARGUEMENT
            self.add_tracking("%s.%s" % (new_ns, a.arg), "%s.%s" % (new_ns, "<arg" + str(cnt) + ">"))

        # TODO: Add for kwargs
        #for a in node.args.kwonlyargs:
        #    pass

        # only last n arguements have defaults
        start = len(node.args.args) - len(node.args.defaults)
        for cnt, d in enumerate(node.args.defaults, start=start):
            self.visit(d)
            # iterate definitions to find on which positional arguement
            # the default is applied, and if it is a function update
            # the arguement's points to set
            func_name = self.find_ns(d.id)
            for name, definition in self.scopes[new_ns].defs.items():
                if definition.get("position", None) == cnt:
                    definition["points"] = definition["points"].union(set([func_name]))

        # TODO
        #for d in node.args.kw_defaults:
        #    self.visit(d)

        for stmt in node.body:
            self.visit(stmt)

        # Exiting function contents. Extract scope and function name from stack
        self.scope_stack.pop()
        self.name_stack.pop()

    def visit_Call(self, node):
        # If we can find a namespace for the current node name
        # then we can iterate the arguments passed into the function
        # call, and for each one of them which is an instance of `ast.Name`
        # find its points_to set and update the corresponding argument on the function def.
        current_ns = self.get_current_namespace()
        def add_points_to_args(ns):
            for cnt, a in enumerate(node.args):
                if isinstance(a, ast.Call):
                    target_ns = "%s.<return>" % self.find_ns(a.func.id)
                    follow = False
                if isinstance(a, ast.Name):
                    target_ns = self.find_ns(a.id)
                    follow = True
                if ns:
                    self.add_tracking("%s.%s" % (ns, "<arg" + str(cnt) + ">"), target_ns, follow)

        ns = self.find_ns(node.func.id)
        if ns:
            add_points_to_args(ns)
        else:
            for fid in self.find_points_to(node.func.id):
                add_points_to_args(fid)

        self.visit(node.func)

    def visit_Return(self, node):
        if isinstance(node.value, ast.Call):
            self.visit(node.value)
            ns = "%s.<return>" % self.find_ns(node.value.func.id)
            follow = False
        if isinstance(node.value, ast.Name):
            ns = self.find_ns(node.value.id)
            follow = True
        if ns:
            current_ns = self.get_current_namespace()
            self.add_tracking("%s.%s" % (current_ns, "<return>"), ns, follow)

    def visit_Name(self, node):
        """
        When node.ctx is an intance of ast.Load
        then we're talking about a function call.
        First try to find the function either from the imports
        or from the upper scopes.
        If not found just add an edge to the node.id.
        """
        if isinstance(node.ctx, ast.Load):
            current_namespace = self.get_current_namespace()
            ns = self.find_ns(node.id)
            t = self.find_type(node.id)
            if t == Scope.FUNCTION_DEF:
                known = True
            else:
                known = False
            self.cg.add_edge(current_namespace, ns, known)

    def visit_Assign(self, node):
        stack_head = self.scope_stack[-1][1]
        for target in node.targets:
            stack_head.defs[target.id]["type"] = Scope.VAR_DEF
        ns = None
        if isinstance(node.value, ast.Call):
            self.visit(node.value)
            ns = "%s.<return>" % self.find_ns(node.value.func.id)
            follow = False
        if isinstance(node.value, ast.Name):
            ns = self.find_ns(node.value.id)
            follow = True

        if ns:
            current_ns = self.get_current_namespace()
            for target in node.targets:
                self.add_tracking("%s.%s" % (current_ns, target.id), ns, follow)


    def analyze_submodules(self):
        for module, filename in self.submodules:
            if module in self.modules_analyzed:
                continue
            submodule_graph = Visitor(module, filename, modules_analyzed=self.modules_analyzed)
            submodule_graph.analyze()
            self.functions += submodule_graph.functions
            self.merge_tracking(submodule_graph.tracking)
            self.cg.merge_subgraph(submodule_graph.cg)
            self.merge_scopes(submodule_graph.get_scopes())
            self.merge_analyzed_for(module, submodule_graph.modules_analyzed)

    def analyze(self):
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()
        self.visit(ast.parse(self.contents, self.filename))
        transitive = transitive_closure(self.tracking)
        for t in transitive:
            new_ls = []
            for name in transitive[t]:
                if name in self.functions:
                    new_ls.append(name)
            transitive[t] = new_ls
        self.cg.add_transitive(transitive)
        self.cg.add_functions(self.functions)
