
class Meta(type):
    def create(cls):
        return cls()
    def describe(cls): pass
class Model(metaclass=Meta):
    def __init__(self): pass
    def describe(self): pass
class Plain:
    pass
Model.create()
Model().describe()
def plain():
    Plain.mro()
    Plain.__name__.lower()
