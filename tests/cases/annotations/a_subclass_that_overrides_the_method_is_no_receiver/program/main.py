
class Base:
    def run(self):
        self.step()
    def step(self): pass
    @classmethod
    def make(cls):
        cls.step(None)
class Child(Base):
    def run(self): pass
    def step(self): pass
    @classmethod
    def make(cls): pass
class Heir(Base):
    def step(self): pass
