class C:
    def m(self): pass
for k in {C(): 1}.keys(): k.m()