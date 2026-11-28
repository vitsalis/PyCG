
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass
class Setter:
    def __set__(self, obj, value): pass
def setter_base():
    return Setter
class Field(setter_base()):
    def __get__(self, obj, owner=None): return Rows()
class WithField:
    value = Field()
def late():
    return WithField
class Model(late()):
    pass
def use(model):
    model.value = Pairs()
    model.value.index(1)
use(Model())
