
def f(): pass
class Meta(type):
    def __len__(cls):
        return 0
    def __iter__(cls):
        cls.members()
        return iter([f])
    def __add__(cls, other):
        pass
    def __repr__(cls):
        return ""
    def __contains__(cls, item):
        return False
    def __enter__(cls):
        return cls
    def __exit__(cls, *exc):
        pass
class Colors(metaclass=Meta):
    @classmethod
    def members(cls): pass
class Plain:
    def __len__(self):
        return 0
def use():
    len(Colors)
    for color in Colors:
        color()
    Colors + 1
    repr(Colors)
    1 in Colors
    with Colors:
        pass
    len(Plain)
