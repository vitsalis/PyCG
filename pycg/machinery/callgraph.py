class CallGraph(object):
    def __init__(self):
        self.cg = {}

    def add_node(self, name):
        if not isinstance(name, str):
            raise CallGraphError("Only string node names allowed")
        if not name:
            raise CallGraphError("Empty node name")

        if not name in self.cg:
            self.cg[name] = set()

    def add_edge(self, src, dest):
        self.add_node(src)
        self.add_node(dest)
        self.cg[src].add(dest)

    def get(self):
        return self.cg

class CallGraphError(Exception):
    pass
