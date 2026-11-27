
class Base:
    def run(self): pass
class Child(Base):
    __slots__ = ("run",)
    __slots__ = ()
Child().run()
