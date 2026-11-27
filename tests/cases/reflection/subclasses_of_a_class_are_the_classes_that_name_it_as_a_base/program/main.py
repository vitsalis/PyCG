
class Base:
    def run(self): pass
class A(Base):
    def run(self): pass
class B(Base):
    def run(self): pass
class C(A):
    def run(self): pass
def each():
    for cls in Base.__subclasses__():
        cls().run()
each()
