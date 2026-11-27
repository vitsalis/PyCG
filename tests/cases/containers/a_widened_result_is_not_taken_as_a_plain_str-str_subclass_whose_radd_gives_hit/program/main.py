def f(): pass
def g(): pass
def h(): pass

class Odd(str):
    def __format__(self, spec):
        return self
    def __radd__(self, left):
        return self if left == "pre_" else "hit"
k = "pre_" + f"{Odd('x')}"

table = {"hit": f, "top_x": g}
def read():
    table["top_" + k]()
