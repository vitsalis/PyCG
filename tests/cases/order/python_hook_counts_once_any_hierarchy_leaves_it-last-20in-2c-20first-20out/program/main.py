
def helper(): pass
class Hooked:
    def __getattribute__(self, name):
        pass
class Plain:
    pass
def a(): return b()
def b(): return c()
def c(): return Plain
class Holder:
    pass
holder = Holder()
holder.base = Hooked
holder.base = a()
class C(holder.base):
    @property
    def value(self):
        helper()
def use():
    C().value
