
class Needle:
    def __eq__(self, other): return False
class M1(type):
    def __contains__(cls, other): return False
class M2(M1): pass
class M3(M1): pass
def use(meta):
    class Bag(metaclass=meta): pass
    return Needle() in Bag
for meta in (M1, M2, M3):
    use(meta)
