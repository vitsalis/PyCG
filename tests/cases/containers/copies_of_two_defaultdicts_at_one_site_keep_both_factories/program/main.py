def f(): pass
def g(): pass
def h(): pass

from collections import defaultdict
def copy(d):
    return d.copy()
copy(defaultdict(f))
d = copy(defaultdict(g))
d["k"]()
