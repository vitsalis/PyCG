
class Base:
    def method(self): pass
class Child(Base):
    method: object
Child().method()
