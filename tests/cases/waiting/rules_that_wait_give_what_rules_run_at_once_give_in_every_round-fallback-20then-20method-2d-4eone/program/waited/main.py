
class C:
    def __getattr__(self, name): pass
def length(self): return 1
def later(): return lambda: lambda: length
def use(x):
    len(x)
def other(x):
    len(x)
use(C())
other(C())
c = C()
C.__len__ = later()()()
len(c)
