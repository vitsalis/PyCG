class ClassManager:
    def __init__(self):
        self.names = {}

    def get(self, name):
        if name in self.names:
            return self.names[name]

    def create(self, name):
        cls = ClassNode(name)
        self.names[name] = cls
        return cls

class ClassNode:
    def __init__(self, ns):
        self.ns = ns
        self.parents = []

    def add_parent(self, parent):
        if isinstance(parent, str):
            self.parents.append(parent)
        elif isinstance(parent, list):
            self.parents += parent

    def get_mro(self):
        return self.parents

    def compute_mro(self):
        res = []
        self.parents.reverse()
        for parent in self.parents:
            if not parent in res:
                res.append(parent)

        res.reverse()
        self.parents = res
