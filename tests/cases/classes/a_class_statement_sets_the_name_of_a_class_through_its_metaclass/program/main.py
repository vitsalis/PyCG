
class Meta(type):
    def __set_name__(cls, owner, name):
        pass
class C(metaclass=Meta): pass
class Owner:
    held = C
