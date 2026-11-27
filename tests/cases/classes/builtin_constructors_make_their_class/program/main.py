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
    if isinstance(arg, list):
        for value in arg:
            value.after()
parse(list([A()]))
parse(tuple([B()]))
parse(dict([(Sub(), 1)]))
parse(frozenset([Other()]))
