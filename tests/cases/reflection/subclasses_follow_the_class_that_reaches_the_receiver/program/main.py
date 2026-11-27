
class Base:
    def run(self): pass
class A(Base):
    def run(self): pass
class C(A):
    def run(self): pass
def each(kind):
    for cls in kind.__subclasses__():
        cls().run()
each(A)
