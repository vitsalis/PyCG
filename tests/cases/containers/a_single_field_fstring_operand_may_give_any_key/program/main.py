def f(): pass
def g(): pass
def h(): pass

class Odd(str):
    def __radd__(self, other):
        return "hit"
class Wrap:
    def __format__(self, spec):
        return Odd("x")
table = {"hit": f, "pre_x": g}
def read():
    table["pre_" + f"{Wrap()}"]()
