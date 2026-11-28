
class Base:
    def __getattr__(self, name): pass
    def run(self):
        self.value
class Child(Base):
    __slots__ = ("value",)
Base().run()
