
class Plain: pass
class Meta(type):
    def __new__(mcs, name, bases, namespace): return Plain
    def __init__(cls, name, bases, namespace): pass
class Made(metaclass=Meta): pass
