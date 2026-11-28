
def f(): pass
def g(): pass
def h(): pass
def k(): pass

class C:
    def pick(self, *args):
        return args[0]
    @classmethod
    def make(cls, *args):
        return args[0]
    @staticmethod
    def plain(*args):
        return args[0]
def use():
    C().pick(f)()
    C.make(g)()
    C().plain(h)()
C().pick(k)
C.make(k)
C.plain(k)
