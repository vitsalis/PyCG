class Base:
    def __add__(self, other):
        return self

    def __radd__(self, other):
        return self


class Derived(Base):
    def __radd__(self, other):
        return self


result = Base() + Derived()
