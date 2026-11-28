
def g(): pass
def h(): pass
class Reader:
    def read(self, size=-1, /):
        size()
def f(a, cb=g, /):
    a()
    cb()
Reader().read(h)
f(h)
