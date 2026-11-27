def f(): pass
def g(): pass
def h(): pass

s = set()
s.add(f)
s.update([g])
s.pop()()
