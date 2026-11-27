
import collections
def a(): pass
def b(): pass
def c(): pass
def make(factory, *args):
    return factory(*args)
xs = [a]
ys = {b}
fs = frozenset([c])
d = {"k": a}
q = collections.deque([b])
counts = collections.Counter([c])
made = [
    make(collections.OrderedDict, [("k", b)]),
    make(collections.defaultdict, list, {"k": c}),
    make(collections.defaultdict, make),
    make(collections.Counter, [a]),
    make(collections.deque, [c]),
    make(q.popleft),
    make(q.extendleft, [a]),
    make(counts.update, [b]),
    make(list, (a, b)),
    make(tuple, (a, b, c)),
    make(set, [b]),
    make(frozenset, [c]),
    make(dict, [("k", b)]),
    make(iter, [c]),
    make(iter, a, None),
    make(xs.copy),
    make(ys.copy),
    make(fs.copy),
    make(d.copy),
    make(d.keys),
    make(d.values),
    make(d.items),
    make(xs.extend, [b]),
    make(ys.update, [c], [a]),
    make(d.update, {"j": c}),
    make(xs.pop),
    make(next, iter([b])),
]
for result in made:
    result[0]()
    result[-1]()
    for f in result:
        f()
