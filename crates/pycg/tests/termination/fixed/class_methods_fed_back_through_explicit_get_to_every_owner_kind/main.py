class Meta(type): pass
class C(metaclass=Meta): pass
def make(cls):
    return classmethod(make)
m = classmethod(make)
for _ in range(2):
    m = m.__get__(None, int)()
    m = m.__get__(C)()
    m = m.__get__(C())()
    m = m.__get__(None, m)()
