
import collections
def f(): pass
def g(): pass
def make(cb=f):
    return cb
class Node:
    def same(self):
        return self
    def visit(self): pass
def use():
    collections.defaultdict(make)["a"]()
    collections.defaultdict(Node().same)["b"].visit()
make(g)
use()
