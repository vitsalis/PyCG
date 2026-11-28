class C:
    def m(self): pass
xs = []
xs.insert(0, C())
xs[0].m()