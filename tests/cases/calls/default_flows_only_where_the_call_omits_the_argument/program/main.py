
def g(): pass
def h(): pass
def given(cb=g):
    cb()
def by_keyword(cb=g):
    cb()
def omitted(cb=g):
    cb()
given(h)
by_keyword(cb=h)
omitted()
