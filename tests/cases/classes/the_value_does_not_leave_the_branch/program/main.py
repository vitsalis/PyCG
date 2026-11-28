class A:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Sub(A):
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class B:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Other:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass

def use(x):
    if isinstance(x, A):
        x.inside()
    x.after()
    for _ in range(2):
        if isinstance(x, B):
            x.more()
            continue
        x.other()
def loop(x):
    while True:
        if isinstance(x, A):
            x.inside()
            break
    x.after()
