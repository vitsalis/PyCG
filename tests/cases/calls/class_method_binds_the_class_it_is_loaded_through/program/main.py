
class Base:
    @classmethod
    def create(cls):
        return cls()
class Child(Base):
    def __init__(self): pass
    def run(self): pass
Child.create().run()
Child().create().run()
