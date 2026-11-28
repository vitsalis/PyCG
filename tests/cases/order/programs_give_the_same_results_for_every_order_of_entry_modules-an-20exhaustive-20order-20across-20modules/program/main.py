from a import A1, A2, A3
from b import B1, B2, B3
def pick(i):
    return [A1, B1, A2, B2, A3, B3][i]
class C(pick(0), pick(1)): pass
