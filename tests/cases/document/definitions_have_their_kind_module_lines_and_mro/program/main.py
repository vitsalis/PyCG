import ext
class Base:
    def run(self):
        return lambda: None
class Child(Base, ext.Mixin):
    pass
def outer():
    def inner(): pass
