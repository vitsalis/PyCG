
class Element:
    def __str__(self): return "s"
    def __repr__(self): return "r"
    def __format__(self, spec): return "f"
class Key:
    def __hash__(self): return 0
    def __repr__(self): return "k"
class Inner:
    def __repr__(self): return "i"
def convert(xs):
    b'%.2147483648r' % xs
convert((Element(),))
