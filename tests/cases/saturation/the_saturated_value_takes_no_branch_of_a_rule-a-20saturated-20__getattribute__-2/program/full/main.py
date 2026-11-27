
def g1(self, name): return 1
def g2(self, name): return 1
def g3(self, name): return 1
class Holder:
    __getattribute__ = g1
    @property
    def value(self): return 1
def use(hook):
    Holder.__getattribute__ = hook
    Holder().value
for hook in (g2, g3):
    use(hook)
