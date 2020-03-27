class CallGraph(object):
    def __init__(self):
        self.cg = {}
        self.modnames = {}

    def add_node(self, name, modname=""):
        if not isinstance(name, str):
            raise CallGraphError("Only string node names allowed")
        if not name:
            raise CallGraphError("Empty node name")

        if not name in self.cg:
            self.cg[name] = set()
            self.modnames[name] = modname

        if name in self.cg and not self.modnames[name]:
            self.modnames[name] = modname

    def add_edge(self, src, dest):
        self.add_node(src)
        self.add_node(dest)
        self.cg[src].add(dest)

    def get(self):
        return self.cg

    def get_edges(self):
        output = []
        for src in self.cg:
            for dst in self.cg[src]:
                output.append([src, dst])
        return output

    def get_modules(self):
        return self.modnames

class CallGraphError(Exception):
    pass
