def f(): pass
def g(): pass
def h(): pass
import collections
for v in collections.OrderedDict({'a': f}).values(): v()