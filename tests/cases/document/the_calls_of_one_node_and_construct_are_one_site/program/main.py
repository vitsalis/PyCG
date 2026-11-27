class C:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    @property
    def a(self): pass
    @property
    def b(self): pass
for x in C():
    pass
"{0.a} {0.b}".format(C())
