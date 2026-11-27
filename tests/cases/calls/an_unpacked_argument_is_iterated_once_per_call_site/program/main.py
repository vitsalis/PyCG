def f(): pass
def g(): pass
def h(): pass

class Item:
    action = staticmethod(g)
    def __iter__(self):
        return self
    def __next__(self):
        return self
class Source:
    __iter__ = Item
def set_action(x):
    x.action = f
def invoke(x):
    x.action()
def dispatch(fn, src):
    fn(*src)
dispatch(set_action, Source())
dispatch(invoke, Source())
