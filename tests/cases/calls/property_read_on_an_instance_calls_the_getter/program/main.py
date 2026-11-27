
def g(): pass
class C:
    @property
    def handler(self):
        return g
def use(c):
    c.handler()
use(C())
