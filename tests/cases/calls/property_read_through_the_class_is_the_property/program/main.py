
class C:
    @property
    def value(self): pass
def show(c):
    C.value.fget(c)
