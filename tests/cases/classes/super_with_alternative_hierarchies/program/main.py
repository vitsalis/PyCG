
import sys
class A:
    def run(self): pass
class B:
    def run(self): pass
class C(A if sys.argv else B):
    def run(self):
        super().run()
C().run()
