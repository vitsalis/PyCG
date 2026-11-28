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
parse([A()][0:])
parse([Sub()].copy())
parse((B(),)[0:])
def pairs(mapping):
    for pair in mapping.items():
        if isinstance(pair, list):
            pair[0].after()
        else:
            pair[0].more()
pairs({B(): 1})
def rest(arg):
    first, *others = arg
    if isinstance(others, tuple):
        others[0].other()
rest((A(), B()))
