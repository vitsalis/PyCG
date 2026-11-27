
import ext
def f(): pass
def g(): pass

class Alias:
    def __set_name__(self, owner, name):
        getattr(Registry, name)()
class Registry:
    run = staticmethod(f)
    other = staticmethod(g)
class Model:
    run = Alias()
