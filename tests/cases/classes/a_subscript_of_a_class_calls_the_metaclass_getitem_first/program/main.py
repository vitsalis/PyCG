
def f(): pass
def g(): pass
class Meta(type):
    def __getitem__(cls, key):
        return f
class Palette(metaclass=Meta):
    def __class_getitem__(cls, key):
        return g
class Plain:
    def __class_getitem__(cls, key):
        return g
def use():
    Palette["red"]()
def plain():
    Plain["red"]()
