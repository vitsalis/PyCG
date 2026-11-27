class A:
    def method(self): pass
class B(A): pass
class C(A): pass
def use(base):
    class Unknown(base):
        def method(self):
            super().method()
    class Derived(Unknown): pass
    Unknown()
    Unknown().method()
    for item in Unknown():
        item()
    with Unknown() as entered:
        entered()
    {Unknown(): 1}[Unknown()]()
    (Unknown() + 1)()
    Derived().method()
    try:
        pass
    except Unknown as error:
        error()
for base in (A, B, C):
    use(base)
