
class C:
    def g(self): pass
    def f(self):
        __class__.g(self)
        def nested():
            return __class__
        nested().g(self)
C().f()
