
import ext
class Base:
    def run(self): pass
class Child(Base):
    if ext.flag:
        __slots__ = ("run",)
Child().run()
