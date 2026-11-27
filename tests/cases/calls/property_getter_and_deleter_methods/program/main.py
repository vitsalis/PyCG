
def g(): pass
def h(): pass
class C:
    def __init__(self):
        self.handler = h
    def get(self): pass
    def other(self):
        return g
    def remove(self):
        self.handler()
    plain = property(get)
    regot = plain.getter(other)
    removable = plain.deleter(remove)
c = C()
c.regot()
del c.removable
