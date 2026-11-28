
import collections
def f(): pass
def run():
    d = collections.defaultdict()
    d["a"] = f
    d["a"]()
