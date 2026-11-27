
class Fluent:
    def configure(*args):
        return args[0]
class A(Fluent):
    def run(self): pass
class B(Fluent):
    def run(self): pass
def use():
    A().configure().run()
B().configure().run()
