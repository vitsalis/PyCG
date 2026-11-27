
def g(): pass
class C:
    def get(self):
        return g
    def put(self, value): pass
    def replace(self, value): pass
    plain = property(get, put)
    replaced = plain.setter(replace)
c = C()
c.replaced()
c.replaced = None
