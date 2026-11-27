class C:
    def m(self): pass
for x in frozenset((C(),)).copy(): x.m()