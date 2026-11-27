
class BaseMeta(type):
    def create(cls):
        return cls()
    def describe(cls):
        cls.hook()
class SubMeta(BaseMeta):
    def describe(cls):
        super().describe()
def a(): return b()
def b(): return SubMeta
def base(): return Root
class Root(metaclass=BaseMeta):
    @staticmethod
    def hook(): pass
class Model(base(), metaclass=a()):
    def __init__(self): pass
Chosen = BaseMeta
def choose():
    global Chosen
    Chosen = SubMeta
class Picked(metaclass=Chosen):
    @staticmethod
    def hook(): pass
class Leaf(Model):
    def __init__(self): pass
SubMeta.describe(Model)
Leaf.create()
Picked.describe()
