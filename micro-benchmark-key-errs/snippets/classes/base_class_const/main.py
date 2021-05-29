class Base:
    x = "b"

class Cls(Base):
    def func(self, d):
        d[self.x]

d = {"a": "ab"}

cl = Cls()
cl.func(d)
