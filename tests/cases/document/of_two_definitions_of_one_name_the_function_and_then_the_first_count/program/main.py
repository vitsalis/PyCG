import sys
if sys.argv:
    def f(): pass
else:
    def f():
        pass
class g: pass
def g(): pass
