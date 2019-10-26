class CallGraph(object):
    def __init__(self):
        self.cg = {}

    def add_node(self, name):
        if not name in self.cg:
            self.cg[name] = set()

    def add_edge(self, src, dest):
        self.add_node(src)
        self.cg[src].add(dest)

    def get(self):
        return self.cg
