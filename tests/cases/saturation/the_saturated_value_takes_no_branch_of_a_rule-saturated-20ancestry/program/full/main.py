
import sys
class A(type): pass
class B(type): pass
class C(type): pass
base = A if sys.argv else B if sys.path else C
class Meta(base):
    def __call__(self): pass
def use(value: Meta):
    value()
