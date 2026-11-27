
class Shown:
    def __str__(self): return "s"
    def __repr__(self): return "r"
class Quoted:
    def __str__(self): return "s"
    def __repr__(self): return "r"
def width(s):
    "%*s" % (8, s)
def both(q):
    "%-*.*r" % (8, 2, q)
def mixed(s, q):
    "%.*s %r" % (2, s, q)
width(Shown())
both(Quoted())
mixed(Shown(), Quoted())
