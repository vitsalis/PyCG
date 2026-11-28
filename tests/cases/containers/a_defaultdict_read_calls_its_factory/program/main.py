
import collections
class Node:
    def __init__(self): pass
    def visit(self): pass
class Factory:
    def __call__(self): return g
def make():
    return f
def f(): pass
def g(): pass
def use():
    lists = collections.defaultdict(list)
    lists["a"].append(g)
    for x in lists["a"]:
        x()
    collections.defaultdict(make)["b"]()
    collections.defaultdict(Node)["c"].visit()
    collections.defaultdict(lambda: g)["d"]()
    collections.defaultdict(Factory())["e"]()
use()
