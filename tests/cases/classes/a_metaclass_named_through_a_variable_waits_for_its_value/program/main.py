
class Meta(type): pass
def pick():
    return Meta
class Model(metaclass=pick()): pass
class Made(metaclass=lambda name, bases, namespace: None): pass
def unknown(): pass
class Odd(metaclass=unknown()): pass
