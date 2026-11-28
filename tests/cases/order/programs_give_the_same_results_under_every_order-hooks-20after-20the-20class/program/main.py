
def helper(): pass
def target(): pass
def put(self, name, value):
    value()
def remove(self, name):
    helper()
class Hooked:
    def __getattribute__(self, name):
        pass
class Plain:
    pass
class Holder:
    pass
holder = Holder()
holder.base = Hooked
key = "base"
setattr(holder, key, Plain)
class C(holder.base):
    @property
    def value(self):
        helper()
    @value.setter
    def value(self, new):
        new()
    @value.deleter
    def value(self):
        helper()
C.__setattr__ = put
C.__delattr__ = remove
c = C()
c.value
c.value = target
del c.value
