
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass

import sys
class WithProperty:
    @property
    def value(self): return Rows()
    @value.setter
    def value(self, v): pass
class Without:
    pass
Base = WithProperty if sys.argv else Without
class Model(Base):
    pass
def use(model):
    model.value = Pairs()
    model.value.index(1)
use(Model())
