
def g(): pass
class Plugin:
    def setup(self):
        self.register(make())
    def register(self, factory, hook=g):
        factory()
        hook()
def make():
    return g
