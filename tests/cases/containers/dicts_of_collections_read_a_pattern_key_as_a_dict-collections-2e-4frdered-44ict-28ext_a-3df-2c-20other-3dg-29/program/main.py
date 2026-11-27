def f(): pass
def g(): pass
def h(): pass

import collections
table = collections.OrderedDict(ext_a=f, other=g)
def read(name):
    table["ext_%s" % name]()
read("x")
