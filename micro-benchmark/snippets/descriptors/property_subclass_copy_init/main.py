class named(property):
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        super().__init__(fget, fset, fdel, doc)


def read(self):
    return 1


def write(self, value):
    pass


def add_setter(prop, setter):
    return prop.setter(setter)


class Box:
    size = named(read)
    size = add_setter(size, write)


box = Box()
box.size = 2
box.size
