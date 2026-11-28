
import ext
def f(): pass
def g(): pass

class A: pass
def bases(): return (A,)
class B(*bases()): pass
