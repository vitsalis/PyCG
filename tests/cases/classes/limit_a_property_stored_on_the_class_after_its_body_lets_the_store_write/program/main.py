
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass

class Model:
    pass
def get(self): return Rows()
def put(self, value): pass
Model.value = property(get, put)
def use(model):
    model.value = Pairs()
    model.value.index(1)
use(Model())
