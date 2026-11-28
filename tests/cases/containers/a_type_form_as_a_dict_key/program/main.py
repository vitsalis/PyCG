def f(): pass
def g(): pass
def h(): pass

class A: pass
Alias = list[A]
d = {Alias: f}
d[Alias]()
e = {}
e[Alias] = g
e[Alias]()
