def f(): pass
def g(): pass
def h(): pass

class Base:
    @classmethod
    def hook(cls): pass
class Meta(type):
    def __new__(mcs, *args):
        args[1][0].hook()
        return super().__new__(mcs, *args)
class A(Base, metaclass=Meta): pass
