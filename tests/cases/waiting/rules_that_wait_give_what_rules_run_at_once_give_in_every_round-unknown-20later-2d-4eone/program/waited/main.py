
class A:
    def method(self): pass
class B(A): pass
class C(A): pass
def delay(flag=True):
    return lambda: lambda: lambda: lambda: B if flag else C
base = A
def update():
    global base
    base = delay()()()()()
update()
class Late(base):
    pass
def use(x):
    x.missing()
    x.value = 1
    len(x)
    for item in x:
        item()
    x[0]
    del x.value
use(Late())
use(Late())
