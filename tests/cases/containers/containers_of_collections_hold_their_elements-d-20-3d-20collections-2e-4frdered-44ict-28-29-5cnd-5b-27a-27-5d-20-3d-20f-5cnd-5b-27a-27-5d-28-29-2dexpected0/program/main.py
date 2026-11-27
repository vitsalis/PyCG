def f(): pass
def g(): pass
def h(): pass
import collections
d = collections.OrderedDict()
d['a'] = f
d['a']()