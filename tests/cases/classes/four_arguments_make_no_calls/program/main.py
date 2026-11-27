
class Meta(type):
    def __init__(cls, name, bases, namespace): pass
class Base(metaclass=Meta):
    def __init_subclass__(cls): pass
def make():
    type("C", (Base,), {}, None)
make()
