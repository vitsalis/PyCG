
def keep(f):
    return f
def make():
    class C:
        @keep
        def m(self): pass
    @keep
    def local(): pass
    return C
make()
