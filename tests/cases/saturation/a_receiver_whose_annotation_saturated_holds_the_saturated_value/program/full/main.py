import sys
class A:
    def step(self): pass
class B(A): pass
class C(A): pass
T = A if sys.argv else B if sys.path else C
class K:
    def step(self): pass
    def run(self: T):
        self.step()
