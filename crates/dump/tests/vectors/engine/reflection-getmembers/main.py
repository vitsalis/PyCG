from inspect import getmembers


class Base:
    def inherited(self):
        pass


class C(Base):
    def own(self):
        pass


def stored():
    pass


obj = C()
obj.field = stored
for name, value in getmembers(obj):
    value()
for name, value in getmembers(C):
    value(obj)
