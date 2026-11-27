
class Meta(type):
    def describe(cls): pass
class Model(metaclass=Meta):
    pass
class Plain:
    pass
def describe(cls):
    super(Meta, cls).mro()
describe(Model)
describe(Plain)
