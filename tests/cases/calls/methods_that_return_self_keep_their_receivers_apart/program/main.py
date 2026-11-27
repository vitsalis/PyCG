
class Fluent:
    def configure(self):
        return self
class A(Fluent):
    def run(self): pass
class B(Fluent):
    def run(self): pass
def use():
    A().configure().run()
B().configure().run()
