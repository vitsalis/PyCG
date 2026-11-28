import ext
class Decorator:
    apply = classmethod(ext.keep)
deco = Decorator.apply
@deco
def target(): pass
def use():
    target()
