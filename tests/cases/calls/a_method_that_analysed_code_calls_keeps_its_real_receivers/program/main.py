
class Base:
    def run(self):
        self.step()
    def step(self): pass
class Child(Base):
    def step(self): pass
Base().run()
Child()
