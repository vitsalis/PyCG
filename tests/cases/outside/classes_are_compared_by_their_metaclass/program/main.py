
class Meta(type):
    def __lt__(cls, other): return False
class A(metaclass=Meta): pass
class B(metaclass=Meta): pass
def key(x): return A
def by_items():
    sorted([A, B])
def by_key():
    min([1, 2], key=key)
by_items()
by_key()
