import abc, dataclasses, enum, functools, typing
class C:
    def m(self): pass
def g(): pass
typing.runtime_checkable(C()).m()
