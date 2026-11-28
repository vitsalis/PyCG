
class Value:
    def __str__(self): return "s"
    def __repr__(self): return "r"
class Shown:
    def __repr__(self): return "r"
class Added:
    def __repr__(self): return "r"
MESSAGE = "%r is shown"
def use(v, s, a, flag):
    msg = "%s here" if flag else "%r there"
    msg % (v,)
    MESSAGE % s
    text = "%r"
    text %= (a,)
use(Value(), Shown(), Added(), True)
