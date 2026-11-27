
class Meta(type):
    def describe(cls): pass
class Base:
    def run(self): pass
def base():
    return Base
class Late(base()):
    def run(self): pass
class Model(metaclass=Meta):
    pass
class Other:
    def run(self): pass
def pick(cls, x):
    super(cls, x).run()
for x in (Late(), Other(), Late, Model):
    pick(Base, x)
    pick(Meta, x)
