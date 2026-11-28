from a import A
from b import B
def choose(flag):
    if flag: return A
    return B
class C(choose(True)): pass
