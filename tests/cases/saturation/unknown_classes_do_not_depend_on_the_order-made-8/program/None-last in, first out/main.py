
class A: pass
class B: pass
class C: pass
for base in (A, B, C):
    class Made(base):
        def __call__(self): pass
    instance = object.__new__(Made)
    instance()
