class C:
    def m(self): pass
for v in {1: C()}.values(): v.m()