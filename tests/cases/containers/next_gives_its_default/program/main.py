
class C:
    def m(self): pass
next(iter(()), C()).m()
