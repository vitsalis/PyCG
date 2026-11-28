def f(): pass
def g(): pass
def h(): pass

import collections
def call(a):
    a()
d = collections.OrderedDict(a=f)
dict(d)["a"]()
call(**collections.defaultdict(None, a=g))
for x in list(collections.deque([h])):
    x()
