
def a(): pass
def b(): pass
class Base:
    def __getattr__(self, name):
        return b
class Sub(Base):
    def __getattr__(self, name):
        return a
Sub().missing()
