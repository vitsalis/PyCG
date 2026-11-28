
class Box:
    pass
def f(): pass
def g(): pass
a = Box()
b = Box()
a.run = f
b.run = g
a.run()
