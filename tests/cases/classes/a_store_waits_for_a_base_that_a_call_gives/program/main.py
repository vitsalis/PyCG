
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass

class WithProperty:
    @property
    def value(self): return Rows()
    @value.setter
    def value(self, v): pass
def base():
    return WithProperty
def use(model):
    model.value = Pairs()
    model.value.index(1)
class Model(base()):
    pass
use(Model())
