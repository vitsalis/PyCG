def f(): pass
def g(): pass
def h(): pass

d = {None: f for _ in (1,)}
l = [None for _ in (1,)]
d[None]()
