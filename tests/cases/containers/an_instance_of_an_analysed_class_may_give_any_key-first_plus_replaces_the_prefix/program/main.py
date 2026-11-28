def f(): pass
def g(): pass
def h(): pass

class Odd:
    def __radd__(self, other):
        return "hit_tail"
    def __rmod__(self, other):
        return "hit_tail"
table = {"hit_tail": f, "pre_x": g, "other": h}
def read():
    table["pre_" + Odd() + "_tail"]()
