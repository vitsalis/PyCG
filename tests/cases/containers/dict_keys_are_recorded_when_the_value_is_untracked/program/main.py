def f(): pass
def g(): pass
def h(): pass

class C:
    def m(self): pass
callbacks = {f: None}
for callback in callbacks:
    callback()
d = {}
d.setdefault(g)
for key in d:
    key()
def names(**kw):
    for name in kw:
        getattr(C, name)(C())
names(m=None)
