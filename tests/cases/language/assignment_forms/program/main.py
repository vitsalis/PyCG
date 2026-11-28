
def a(): pass
def b(): pass
def c(): pass
class Holder:
    pass
h = Holder()
x: object = a
h.slot = []
h.slot += [b]
y = z = c
x()
h.slot[0]()
z()
