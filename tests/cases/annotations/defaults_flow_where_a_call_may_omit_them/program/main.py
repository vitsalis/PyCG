
def g(): pass
def h(): pass
def given(cb=g, *, key=g):
    cb()
    key()
given(h, key=h)
def omitted(cb=g):
    cb()
omitted()
