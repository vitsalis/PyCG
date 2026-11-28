def f(): pass
def g(): pass
def h(): pass

d = {"a": f}
d.update({"b": g}, c=h)
d["b"]()
d.get("c")()
d.setdefault("e", f)()
d.pop("a")()
