
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass

def make(member):
    class Model:
        value = member
    model = Model()
    model.value = Pairs()
    model.value.index(1)
