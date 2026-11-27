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

def parse(arg):
    if isinstance(arg, tuple):
        for value in arg:
            value.inside()
    if isinstance(arg, (set, dict)):
        for value in arg:
            value.after()
parse([A() for _ in range(1)])
parse(B() for _ in range(1))
parse({Sub(): 1 for _ in range(1)})
parse((Other(),))
