
def work(): pass
class C:
    __slots__ = ()
c = C()
c.x = work
c.x()
