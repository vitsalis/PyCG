def helper(): pass
class Lazy:
    def __getattr__(self, name): return helper
class Real:
    def method(self): pass
def make(base):
    class Made(base, Lazy): pass
    Made().method()
def first(): return make
def second(): return make
def third(): return make
for factory in (first, second, third):
    factory()(Real)
