
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass

class Table:
    def get(self): return Rows()
    def put(self, value): pass
    headers = property(get, put)
    @property
    def fixed(self): return Rows()
def use(table):
    table.headers = Pairs()
    table.headers.index(1)
    table.fixed = Pairs()
    table.fixed.index(1)
use(Table())
