def f(): pass
def g(): pass
def h(): pass

import collections
d = collections.OrderedDict(a=f)
d.copy()["a"]()
d.copy().get("a")
