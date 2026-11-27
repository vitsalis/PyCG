
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass

class Lazy:
    def __get__(self, obj, owner=None): return Rows()
class Model:
    __slots__ = ("slot",)
    lazy = Lazy()
    annotated: int
    def method(self): pass
class Plain:
    pass
def lazy(model):
    model.lazy = Pairs()
    model.lazy.index(1)
def slot(model):
    model.slot = Pairs()
    model.slot.index(1)
def annotated(model):
    model.annotated = Pairs()
    model.annotated.index(1)
def method(model):
    model.method = Pairs()
    model.method.index(1)
def plain(obj):
    obj.value = Pairs()
    obj.value.index(1)
lazy(Model())
slot(Model())
annotated(Model())
method(Model())
plain(Plain())
