
class Parser:
    def parse(self):
        self.step()
        self.handler()
    def step(self): pass
    @staticmethod
    def check(value):
        value.step()
class Child(Parser):
    def step(self): pass
