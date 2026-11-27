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

def star(*args, **kwargs):
    if isinstance(args, list):
        args[0].inside()
    if isinstance(args, tuple):
        args[0].after()
    if isinstance(kwargs, tuple):
        kwargs["k"].other()
    if isinstance(kwargs, dict):
        kwargs["k"].more()
star(A(), k=B())
