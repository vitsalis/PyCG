
class Wrong:
    def ping(self): pass
x = None
class C:
    global x
    x = None
def set_y():
    global y
    y = None
def use_x():
    x.ping()
def use_y():
    y.ping()
def outer():
    z = None
    def inner():
        nonlocal z
        z = None
    inner()
    z.ping()
