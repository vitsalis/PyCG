import ext
class Decorator:
    __call__ = staticmethod(ext.keep)
deco = Decorator()
@deco
def target(): pass
def use():
    target()
