import abc, dataclasses, enum, functools, typing
class C:
    def m(self): pass
def g(): pass
functools.total_ordering(C()).m()
