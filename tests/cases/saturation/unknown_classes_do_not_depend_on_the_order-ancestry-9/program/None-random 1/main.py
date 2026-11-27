
class Root:
    def __init_subclass__(cls): pass
    def method(self): pass
class Left(Root):
    def left(self): pass
class A(Root):
    def __init_subclass__(cls): pass
    def method(self): pass
class B(Root):
    def __init_subclass__(cls): pass
class C(Root):
    def __init_subclass__(cls): pass
def make(base):
    class Child(Left, base):
        def own(self): pass
        def calls_super(self):
            super().method()
    child = Child()
    child.own(); child.left(); child.method(); child.calls_super()
    Child.own(child)
for base in (A, B, C):
    make(base)
