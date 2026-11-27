
class M1(type):
    def __getitem__(cls, key): pass
class M2(M1): pass
class M3(M1): pass
def use(meta):
    class Bag(metaclass=meta):
        def __class_getitem__(cls, key): pass
    Bag[0]
for meta in (M1, M2, M3):
    use(meta)
