
class Wrong:
    def ping(self): pass
class C:
    global __x
    __x = None
class D:
    _D__x: object
    __x = None
    __y = None
def use_c():
    _C__x.ping()
def use_dx():
    D._D__x.ping()
def use_dy():
    D._D__y.ping()
