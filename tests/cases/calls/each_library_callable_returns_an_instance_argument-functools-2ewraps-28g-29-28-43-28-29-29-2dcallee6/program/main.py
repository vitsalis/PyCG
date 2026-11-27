import abc, dataclasses, enum, functools, typing
class C:
    def m(self): pass
def g(): pass
functools.wraps(g)(C()).m()
