import abc, dataclasses, enum, functools, typing
class C:
    def m(self): pass
def g(): pass
functools.update_wrapper(C(), g).m()
