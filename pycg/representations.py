class Scope(object):
    # scope defs
    CLASS_DEF       = "CLASS_DEF"
    IMPORT_DEF      = "IMPORT_DEF"
    VAR_DEF         = "VAR_DEF"
    FUNCTION_DEF    = "FUNCTION_DEF"
    ARGUEMENT        = "ARGUEMENT"
    UNKNOWN         = "UNKNOWN"

    def __init__(self, table, parent_ns, parent_defs):
        self.name = table.get_name() if table.get_name() != 'top' else ''
        self.type = table.get_type()
        self.returns_to = set()
        self.ns = "%s.%s" % (parent_ns, self.name) if self.name else parent_ns
        self.defs = {i: {"type": self.UNKNOWN, "points": set()} for i in table.get_identifiers()}

    def add_def(self, name, def_type, def_name):
        self.defs[name]["type"] = def_type
        self.defs[name]["points"] = set([def_name])

    def __repr__(self):
        return "<Scope: %s %s -- %s Returns: %s>" % (self.name, self.type, str(self.defs), str(self.returns_to))

class Node(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<Node: %s>"% self.name

class CallGraph(object):
    def __init__(self, cg=None):
        # TODO: Work on the format of the graph
        self.cg = {}
        self.transitive = {}
        self.functions = []
        if cg:
            self.cg = cg.output()

    def output_full(self):
        for name in self.cg:
            for unknown in self.cg[name]["unknown"]:
                if unknown in self.transitive:
                    self.cg[name]["known"] = list(set(self.cg[name]["known"] + self.transitive[unknown]))
                if unknown in self.functions and unknown not in self.cg[name]["known"]:
                    self.cg[name]["known"].append(unknown)
        return self.cg

    def output(self):
        old_cg = self.output_full()
        new_cg = {}
        for name in old_cg:
            new_cg[name] = old_cg[name]["known"]
        return new_cg

    def add_transitive(self, transitive):
        self.transitive = transitive

    def add_functions(self, functions):
        self.functions = functions

    def merge_subgraph(self, graph):
        if not isinstance(graph, CallGraph):
            raise Exception("Input graph must be of type CallGraph")

        # Gets the graph of a module and merges it with
        # the current graph
        for k, v in graph.output_full().items():
            if hasattr(self.cg, k):
                # merge and remove duplicates
                self.cg[k] = list(dict.fromkeys(self.cg[k] + graph[k]))
            else:
                self.cg[k] = v

    def add_node(self, name):
        if self.cg.get(name, None):
            return

        self.cg[name] = {
            "known": [],
            "unknown": []
        }

    def add_edge(self, src, dst, known=True):
        if not self.cg.get(src, None):
            self.add_node(src)

        if known and dst not in self.cg[src]["known"]:
            self.cg[src]["known"].append(dst)
        elif dst not in self.cg[src]["unknown"]:
            self.cg[src]["unknown"].append(dst)
