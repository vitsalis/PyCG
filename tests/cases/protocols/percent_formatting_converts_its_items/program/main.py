
class Value:
    def __str__(self): return "s"
    def __repr__(self): return "r"
class Named:
    def __str__(self): return "n"
class Number:
    def __str__(self): return "x"
def use(v, n, w):
    "%s and %r" % (v, v)
    "%(name)s" % {"name": n}
    "%d%%" % w
use(Value(), Named(), Number())
