
class Base:
    def run(self):
        self.step()
    def step(self): pass
class Child(Base):
    run = Base.run
    def step(self): pass
