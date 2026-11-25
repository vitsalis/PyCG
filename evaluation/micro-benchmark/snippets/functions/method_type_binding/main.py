import types


def describe(self):
    return self.label


class Box:
    label = "box"


box = Box()
box.describe = types.MethodType(describe, box)
box.describe()
