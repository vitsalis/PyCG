class C:
    def m(self): pass
d = {}
d.setdefault(C())
for k in d: k.m()