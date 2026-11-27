def f(): pass
def g(): pass
def h(): pass
import collections
c = collections.Counter()
c.update([g])
for k in c: k()