
class Meta(type):
    def describe(cls): pass
class Model(metaclass=Meta):
    pass
class Plain:
    pass
def describe(cls):
    s = super(Meta, cls)
describe(Model)
describe(Plain)
