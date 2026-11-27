
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass

class Field:
    def __get__(self, obj, owner=None): return Rows()
    def __set__(self, obj, value): pass
class Removable:
    def __get__(self, obj, owner=None): return Rows()
    def __delete__(self, obj): pass
class Model:
    field = Field()
    removable = Removable()
def use(model):
    model.field = Pairs()
    model.field.index(1)
    model.removable = Pairs()
    model.removable.index(1)
use(Model())
