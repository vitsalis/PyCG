import sys
import os
import ast

from pycg.representations import Node, Scope, CallGraph

from pycg.utils import analyze_scopes, discover_locals, to_mod_name, parent_ns, log, transitive_closure, correct_tracking

class Visitor(ast.NodeVisitor):
    def __init__(self, modulename, filename, modules_analyzed=[]):
        # name of file being analyzed
        self.filename = filename
        # parent directory of file
        self.parent_dir = os.path.dirname(filename)
        # name of the module being analyzed
        self.modulename = modulename
        with open(filename, "rt") as f:
            self.contents = f.read()

        # counter for the number of times we've passed the ast
        self.pass_no = 0
        # all modules under the current directory
        self.local_modules = discover_locals(self.parent_dir)
        # dict of Scope objects for each function and module
        self.scopes = analyze_scopes(self.modulename, self.contents, self.filename)
        # Add the current module to the already analyzed list
        self.modules_analyzed = list((set(modules_analyzed + [modulename])))
        # The call graph
        self.cg = CallGraph()
        # List of functions identified in this module so far
        self.functions = []
        # Track for each variable or function the full name it points to
        self.name_tracking = {}
        # Stack for names of functions
        self.name_stack = []
        # Stack for scopes
        self.scope_stack = []
        # List of submodules that are imported in the form
        # of (modname, filename)
        self.submodules = []

    def merge_name_tracking(self, name_tracking):
        """
        Take different name tracking information (supposedly from a submodule)
        and merge it with the name tracking for this module.
        """
        for n in name_tracking:
            if n not in self.name_tracking:
                self.name_tracking[n] = name_tracking[n]

    def add_name_tracking(self, name, target, follow=False):
        """
        Add a mapping between the name provided and its target
        on the `name_tracking` dictionary.
        If `follow == True` then add the targets of `target` to the
        `name_tracking` dictionary.
        """
        if name not in self.name_tracking:
            self.name_tracking[name] = []

        if follow and target in self.name_tracking:
            self.name_tracking[name] = list(set(self.name_tracking[name] + self.name_tracking[target]))
        elif target not in self.name_tracking[name]:
            self.name_tracking[name].append(target)

    def get_current_namespace(self):
        """
        Join the contents of the name stack to get the current namespace
        """
        return ".".join(self.name_stack)

    def output_call_graph(self):
        return self.cg.output()

    def merge_scopes(self, scopes):
        """
        Gets the scopes of a different module
        and merges them with the current scopes.
        """
        for s in scopes:
            if s not in self.scopes:
                self.scopes[s] = scopes[s]

    def get_scopes(self):
        # TODO: maybe give them in a different format???
        return self.scopes

    def merge_modules_analyzed(self, analyzed):
        """
        Gets the modules that a submodule analyzed
        and merges the information with the submodules analyzed by
        this module.
        """
        self.modules_analyzed = list(set(self.modules_analyzed + analyzed))

    def find_scope_type(self, name):
        """
        Iterates the scope stack in order to find a defined type
        for a given name.
        If no type is found then UNKNOWN is returned.
        """
        for ns, scope in reversed(self.scope_stack):
            if name in scope.defs:
                if scope.defs[name]["type"] != Scope.UNKNOWN:
                    return scope.defs[name]["type"]

        return Scope.UNKNOWN

    def find_ns(self, name):
        """
        Iterates the name stack in order to find the namespace a name
        was defined.
        In the case a name comes from an import use the name of the imported
        module for the namespace.
        """
        for ns, scope in reversed(self.scope_stack):
            if name in scope.defs:
                if scope.defs[name]["type"] == Scope.IMPORT_DEF:
                    return list(scope.defs[name]["points"])[0]
                if scope.defs[name]["type"] != Scope.UNKNOWN:
                    return "%s.%s" % (ns, name)

    def find_points_to(self, name):
        """
        Gets a function name and visits the scope stack in a reverse order
        looking for a function definition matching the name.
        """
        for ns, scope in reversed(self.scope_stack):
            if name in scope.defs:
                if len(scope.defs[name]["points"]):
                    return scope.defs[name]["points"]
        return set()

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
            - Get the scope of the parent and add a reference to
                the imported module under defs dictionary
            - Find if the module has an __init__ file and add it for analysis
        """

        def retrieve_local(name):
            """
            Recursivelly iterate the name to find out
            in which module it belongs to.
            """
            if not name:
                return None, None

            if name in self.local_modules:
                return (name, self.local_modules[name])
            splitted = name.split(".")
            return retrieve_local(".".join(splitted[:-1]))

        def add_module_info(module, filename, tgt_name, points_to):
            """
            Takes a module, adds it to the submodules list
            and then adds the imported information to the
            Scope object of the parent.
            """
            if (module, filename) not in self.submodules:
                self.submodules.append((module, filename))

            # Modify the current scope to contain the imported module
            stack_head = self.scope_stack[-1][1]

            # handle * imports
            if tgt_name == "*" and self.scopes.get(module, None):
                for tgt in self.scopes[module].defs:
                    stack_head.add_def(tgt, Scope.IMPORT_DEF, "%s.%s" % (module, tgt))
            elif tgt_name != "*":
                stack_head.add_def(tgt_name, Scope.IMPORT_DEF, points_to)

        def find_and_add_init(modname, filename, tgt_name, points_to):
            """
            Finds if a module has an __init__.py file and if yes
            it adds it for analysis.
            """
            init_mod = ".".join(modname.split(".")[:-1]) + "." + "__init__"
            if init_mod.startswith("."):
                init_mod = init_mod[1:]

            init_path = os.path.join("/".join(filename.split("/")[:-1]), "__init__.py")
            if os.path.exists(init_path):
                add_module_info(init_mod, init_path, tgt_name, points_to)

        for import_item in node.names:
            # Retrieve actual name and asname
            src_name = import_item.name
            tgt_name = import_item.asname if import_item.asname is not None else src_name

            # prefix is the <from_name>
            points_to = prefix + "." + src_name if prefix else src_name

            # only the last part of the import is kept in the namespace
            tgt_name = tgt_name.split(".")[-1]
            module, filename = retrieve_local(points_to)
            if module and filename:
                # level is for relative imports
                if level > 0:
                    modname = self.modulename
                    # Iterate parent modules to find the correct module
                    while level > 0:
                        modname = parent_ns(modname)
                        level -= 1
                    if modname:
                        points_to = modname + "." + points_to
                        module = modname + "." + module

                add_module_info(module, filename, tgt_name, points_to)
                find_and_add_init(module, filename, tgt_name, points_to)
            else:
                # It is a third party module, just add a node for it
                self.cg.add_node(points_to)

    def visit_ImportFrom(self, node):
        """
        This case is handled by adding a prefix to visit_Import
        """
        self.visit_Import(node, prefix=node.module, level=node.level)

    def visit_FunctionDef(self, node):
        """
        Handles a function definition.
        First, add a node in the graph for the function.
        Then, iterate each argument and add tracking information for it.
        Finally, visit the statements of the function.
        """
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
            self.add_name_tracking("%s.%s" % (new_ns, a.arg), "%s.%s" % (new_ns, "<arg" + str(cnt) + ">"))

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
        """
        Handles a function call.
        If we can find the namespace of the function being called
        then add points to information for the args of the function.
        Otherwise add points to information for the args of all
        functions that can be pointed by the variable being called.
        """
        def add_name_tracking_arg(ns, cnt, target, follow=False):
            """
            If we can find a namespace for the current node name
            then we can iterate the arguments passed into the function
            call, and for each one of them which is an instance of `ast.Name`
            find its points_to set and update the corresponding argument on the function def.
            """
            if ns in self.name_tracking:
                for name in self.name_tracking[ns]:
                    self.add_name_tracking("%s.%s" % (name, "<arg" + str(cnt) + ">"), target, follow)
            else:
                self.add_name_tracking("%s.%s" % (ns, "<arg" + str(cnt) + ">"), target, follow)

        def add_points_to_args(ns):
            """
            For each of the arguements of the function
            find out if they are functions, and if they are
            update the points to information of the corresponding
            args on the function definition.
            """
            for cnt, a in enumerate(node.args):
                if isinstance(a, ast.Call):
                    target_ns = "%s.<return>" % self.find_ns(a.func.id)
                    follow = False
                if isinstance(a, ast.Name):
                    target_ns = self.find_ns(a.id)
                    follow = True
                if ns:
                    add_name_tracking_arg(ns, cnt, target_ns, follow)

        ns = self.find_ns(node.func.id)
        if ns:
            add_points_to_args(ns)
        else: # a variable has been called
            for fid in self.find_points_to(node.func.id):
                add_points_to_args(fid)

        self.visit(node.func)

    def visit_Return(self, node):
        """
        Handle return statements.
        Add name tracking information for the value being returned.
        """
        if isinstance(node.value, ast.Call):
            self.visit(node.value)
            ns = "%s.<return>" % self.find_ns(node.value.func.id)
            follow = False
        if isinstance(node.value, ast.Name):
            ns = self.find_ns(node.value.id)
            follow = True
        if ns:
            current_ns = self.get_current_namespace()
            self.add_name_tracking("%s.%s" % (current_ns, "<return>"), ns, follow)

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
            t = self.find_scope_type(node.id)
            if t == Scope.FUNCTION_DEF:
                known = True
            else:
                known = False
            # this is wrong since dir(__builtins__) inside
            # a class, lists only the builtins of classes
            # we need to know the context to resolve the
            # correct builtins
            if not ns and getattr(__builtins__, node.id, None):
                ns = "<built-in>." + node.id

            self.cg.add_edge(current_namespace, ns, known)

    def visit_Assign(self, node):
        """
        Handle assignment statements.
        First, iterate the scope stack and define
            the types of the assigned vars.
        Then, find out what's the value being assigned and
        if it is a function name or a call, add the proper
        name tracking information.
        """
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
                self.add_name_tracking("%s.%s" % (current_ns, target.id), ns, follow)

    def analyze_submodules(self):
        """
        Analyze all submodules, and merge all the call graph, tracking etc
        information with the information for this module.
        """
        for module, filename in self.submodules:
            if module in self.modules_analyzed:
                continue
            submodule_graph = Visitor(module, filename, modules_analyzed=self.modules_analyzed)
            submodule_graph.analyze()
            self.functions += submodule_graph.functions
            self.merge_name_tracking(submodule_graph.name_tracking)
            self.cg.merge_subgraph(submodule_graph.cg)
            self.merge_scopes(submodule_graph.get_scopes())
            self.merge_modules_analyzed(submodule_graph.modules_analyzed)

    def analyze(self):
        """
        Main analysis.
        First, visit the AST two times, because Python doesn't care
        about function definition ordering, and the AST is parsed
        inline.
        Then, resolve backwards tracking information for the name tracking
        completed.
        Finally, perform a transitive closure on the name_tracking information
        in order to resolve where everything points to and produce
        the call graph.
        """
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()
        self.visit(ast.parse(self.contents, self.filename))

        self.name_tracking = correct_tracking(self.name_tracking)
        transitive = transitive_closure(self.name_tracking)
        for t in transitive:
            new_ls = []
            for name in transitive[t]:
                if name in self.functions:
                    new_ls.append(name)
            transitive[t] = new_ls
        self.cg.add_transitive(transitive)
        self.cg.add_functions(self.functions)
