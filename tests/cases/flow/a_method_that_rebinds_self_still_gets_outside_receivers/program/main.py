
def f(): pass
def g(): pass
def h(): pass

class Base:
    def run(self, reset=False):
        if reset:
            self = Base()
        self.step()
    def step(self):
        pass
class Child(Base):
    def step(self):
        pass
child = Child()
