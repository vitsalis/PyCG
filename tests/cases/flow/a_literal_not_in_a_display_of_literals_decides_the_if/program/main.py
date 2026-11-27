
def f(): pass
def g(): pass
def h(): pass

mode = "a"
if mode not in ("a", "b"):
    f()
else:
    g()
