
class Meta(type):
    def __new__(mcs, name, bases, namespace):
        return super().__new__(mcs, name, bases, namespace)
    def __init__(cls, name, bases, namespace):
        pass
class Base(metaclass=Meta):
    def __init_subclass__(cls):
        pass
class Plain:
    def __init_subclass__(cls):
        pass
def build(name):
    type(name, (Base,), {})
    type(name, (Plain,), {})
build("C")
