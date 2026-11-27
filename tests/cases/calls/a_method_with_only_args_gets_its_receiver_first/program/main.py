
def target(): pass
class Base:
    def run(*args):
        args[0].step()
        args[1]()
    def step(self): pass
class Child(Base):
    def step(self): pass
Base().run(target)
Child()
