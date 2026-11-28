
def g(): pass
class C:
    def get(self):
        return g
    def put(self, value): pass
    item = property(get, put)
c = C()
c.item()
c.item = g
