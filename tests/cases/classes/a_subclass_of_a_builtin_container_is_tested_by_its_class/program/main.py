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

class Items(list):
    def inside(self): pass
    def after(self): pass
def parse(arg):
    if isinstance(arg, tuple):
        arg.inside()
    if isinstance(arg, list):
        arg.after()
parse(Items())
