def f(): pass
def g(): pass
def h(): pass

xs = []
xs.append(*(f,))
xs[0]()
d = {}
d.setdefault(*("k", g))
d["k"]()
d.get(*("missing",), **{"default": h})
{}.get("x", *(h,))()
