
import collections
def f(): pass
def g(): pass
q = collections.deque([None])
keys = [0]
q[keys[0]] = f
q.appendleft(None)
q[1]()
q[-1] = g
keys.append(1)
q[keys[-1]]()
