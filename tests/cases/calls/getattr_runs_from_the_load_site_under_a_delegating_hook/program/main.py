
class C:
    def __getattribute__(self, name):
        return object.__getattribute__(self, name)
    def __getattr__(self, name):
        return None
def use(c):
    c.missing
use(C())
