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

def make():
    return Other()
def read():
    module_value.after()
module_value = make()
if isinstance(module_value, A):
    module_value.inside()
class K:
    value = make()
    if not isinstance(value, B):
        raise TypeError(value)
    value.other()
K.value.more()
