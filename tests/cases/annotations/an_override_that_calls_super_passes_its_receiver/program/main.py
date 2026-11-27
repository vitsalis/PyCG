
import ext
class Base:
    def run(self):
        self.step()
    def step(self): pass
class Child(Base):
    def run(self):
        if ext.flag:
            super().run()
    def step(self): pass
