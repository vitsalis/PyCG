def f(): pass
def g(): pass
def h(): pass
import collections
for k, v in collections.Counter([f]).items(): k()