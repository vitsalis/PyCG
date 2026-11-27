
class C:
    pass
def use(x):
    return x.read, x.written, x.set
c = C()
use(c)
c.written = use
setattr(c, "set", use)
