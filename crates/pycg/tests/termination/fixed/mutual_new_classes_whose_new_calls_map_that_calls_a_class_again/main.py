class Caller:
    __call__ = map
class X: pass
class Y: pass
X.__new__ = Y
Y.__new__ = X
Y.__new__ = Caller()
Y([1])
