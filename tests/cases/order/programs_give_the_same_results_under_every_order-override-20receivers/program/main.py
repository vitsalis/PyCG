
class Base:
    def run(self):
        self.step()
    def step(self): pass
    @classmethod
    def make(cls):
        cls.step(None)
class Child(Base):
    def run(self):
        super().run()
    def step(self): pass
def base():
    return Base
class Late(base()):
    def step(self): pass
    @classmethod
    def make(cls): pass
Child()
Late()
