
def f(): pass
def g(): pass
def h(): pass

import ext
def imported():
    from ext import f
    f()
def defined():
    g = ext.make
    def g(): pass
    g()
class Accumulator:
    def __iadd__(self, other):
        return other
    def __call__(self):
        pass
def augmented():
    handler = Accumulator()
    handler += f
    handler()
def walrus():
    handler = f
    (handler := g)
    handler()
