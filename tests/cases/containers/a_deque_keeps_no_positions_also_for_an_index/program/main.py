def f(): pass
def g(): pass
def h(): pass

import collections
def use():
    q = collections.deque([None])
    q[0] = f
    q.appendleft(None)
    q[1]()
    r = collections.deque()
    r.append(g)
    r[-1]()
    xs = [None, h]
    xs[0] = f
    xs[1]()
use()
