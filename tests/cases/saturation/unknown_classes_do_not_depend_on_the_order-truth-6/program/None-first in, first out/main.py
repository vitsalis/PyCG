
class M1(type):
    def __bool__(cls): return True
class M2(M1): pass
class M3(M1): pass
def pick(value): return value
base = M1
for candidate in (M2, M3):
    base = pick(candidate)
class Meta(base):
    def __len__(cls): return 0
class Value(metaclass=Meta): pass
if Value:
    pass
