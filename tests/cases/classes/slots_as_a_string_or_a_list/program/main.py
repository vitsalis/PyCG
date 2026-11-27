
def work(): pass
class Base:
    def __getattr__(self, name): pass
class One(Base):
    __slots__ = "value"
    def run(self):
        self.value
class Many(Base):
    __slots__ = ["first", "second"]
    def run(self):
        self.second
