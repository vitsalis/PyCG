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

def empty(x=Other()):
    if not isinstance(x, ()):
        x.inside()
    if isinstance(x, ()):
        x.after()
def unknown(x=Other(), kinds=None):
    if not isinstance(x, (kinds, kinds)):
        x.other()
def target():
    pass
def function(x=target):
    if isinstance(x, ()):
        x()
def classes(x=target, kinds=()):
    if isinstance(x, kinds):
        x()
def any_class(x=target):
    if isinstance(x, A):
        x()
