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

def attribute(self):
    if isinstance(self.x, A):
        self.x.inside()
def rebound(x, isinstance):
    if isinstance(x, A):
        x.inside()
def helper(x):
    if is_a(x):
        x.inside()
def is_a(x):
    return isinstance(x, A)
def computed(x):
    if isinstance(x, type(A())):
        x.inside()
def global_name():
    global G
    if isinstance(G, A):
        G.inside()
