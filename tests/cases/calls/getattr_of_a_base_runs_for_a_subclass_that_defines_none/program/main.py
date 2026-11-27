
def target(): pass
class Base:
    def __getattr__(self, name):
        return target
class Sub(Base):
    pass
Sub().missing()
