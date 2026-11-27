
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass

class Field:
    def __get__(self, obj, owner=None): return Rows()
    def __set__(self, obj, value): obj.written()
class Lazy:
    def __get__(self, obj, owner=None): return Rows()
class Model:
    field = Field()
    lazy = Lazy()
    def written(self): pass
    @property
    def fixed(self): return Rows()
def store(model):
    model.field = Pairs()
    model.lazy = Pairs()
    model.fixed = Pairs()
    model.plain = Pairs()
    model.late = Pairs()
def field(model):
    model.field.index(1)
def lazy(model):
    model.lazy.index(1)
def fixed(model):
    model.fixed.index(1)
def plain(model):
    model.plain.index(1)
def late(model):
    model.late.index(1)
for model in (Model(), Model()):
    store(model)
    field(model)
    lazy(model)
    fixed(model)
    plain(model)
    late(model)
Model.late = Field()
