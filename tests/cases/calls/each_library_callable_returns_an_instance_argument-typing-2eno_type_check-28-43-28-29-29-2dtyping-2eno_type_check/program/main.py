import abc, dataclasses, enum, functools, typing
class C:
    def m(self): pass
def g(): pass
typing.no_type_check(C()).m()
