
class Base:
    def run(self):
        self.step()
    def step(self): pass
    def helper(*args):
        args[0].step()
class Child(Base):
    def step(self): pass
class Other(Base):
    pass
Child()
Base().helper()
