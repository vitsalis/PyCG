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
        self.mro = [ns]

    def add_parent(self, parent):
        if isinstance(parent, str):
            self.mro.append(parent)
        elif isinstance(parent, list):
            self.mro += parent

    def get_mro(self):
        return self.mro

    def compute_mro(self):
        res = []
        self.mro.reverse()
        for parent in self.mro:
            if not parent in res:
                res.append(parent)

        res.reverse()
        self.mro = res
