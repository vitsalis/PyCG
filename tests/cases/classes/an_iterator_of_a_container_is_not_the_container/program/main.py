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

def run():
    items = [A()]
    it = iter(items)
    if not isinstance(it, list):
        next(it).inside()
    if not isinstance(items, list):
        items[0].after()
    for value in iter((B(),)):
        value.other()
def parse(arg):
    if isinstance(arg, (list, tuple, dict)):
        for value in arg:
            value.inside()
    if isinstance(arg, object):
        for value in arg:
            value.after()
parse(iter([Sub()]))
parse(iter(iter({Other(): 1})))
