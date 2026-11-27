def f(): pass
def g(): pass
def h(): pass
import collections
for k in collections.OrderedDict({g: 1}): k()