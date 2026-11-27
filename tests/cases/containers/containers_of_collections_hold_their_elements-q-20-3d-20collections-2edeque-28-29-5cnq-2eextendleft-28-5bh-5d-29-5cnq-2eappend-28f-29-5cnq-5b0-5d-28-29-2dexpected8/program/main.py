def f(): pass
def g(): pass
def h(): pass
import collections
q = collections.deque()
q.extendleft([h])
q.append(f)
q[0]()