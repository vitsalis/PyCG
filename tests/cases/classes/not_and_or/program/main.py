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

def negated(x):
    if not isinstance(x, A):
        x.inside()
    else:
        x.after()
def both(x, flag):
    if isinstance(x, A) and flag:
        x.inside()
    if isinstance(x, B) or flag:
        x.after()
def neither(x):
    if not (isinstance(x, B) or isinstance(x, Other)):
        x.inside()
    if not isinstance(x, B) and not isinstance(x, Other):
        pass
    else:
        x.after()
def operands(x):
    isinstance(x, A) and x.inside()
    not isinstance(x, B) or x.after()
    x.other() if isinstance(x, Other) else x.more()
