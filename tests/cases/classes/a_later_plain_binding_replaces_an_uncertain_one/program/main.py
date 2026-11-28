
import ext
def work(): pass
class Base:
    def run(self): pass
class Child(Base):
    if ext.flag:
        __slots__ = ()
    __slots__ = ("run",)
child = Child()
child.run = work
child.run()
