
import collections
def f(): pass
def g(): pass
def make(cb=f):
    return cb
class Node:
    def same(self):
        return self
    def visit(self): pass
factories = [make]
d = collections.defaultdict(factories[0])
d["a"]()
factories.append(Node().same)
d["b"].visit()
make(g)
