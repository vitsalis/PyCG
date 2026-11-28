
class P:
    def change(self, value): pass
    item = property(fset=change)
def put(self, name, value):
    object.__setattr__(self, name, value)
P.__setattr__ = put
def use():
    P().item = 1
