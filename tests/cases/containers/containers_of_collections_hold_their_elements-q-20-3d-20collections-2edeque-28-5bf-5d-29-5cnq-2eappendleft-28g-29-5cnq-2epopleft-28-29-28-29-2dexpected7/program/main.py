def f(): pass
def g(): pass
def h(): pass
import collections
q = collections.deque([f])
q.appendleft(g)
q.popleft()()