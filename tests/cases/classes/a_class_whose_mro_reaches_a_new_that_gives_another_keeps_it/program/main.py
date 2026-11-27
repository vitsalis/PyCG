
import ext
def f(): pass
def g(): pass

class Allocating:
    def __new__(cls):
        return super().__new__(cls)
class Factory(Allocating):
    def __new__(cls):
        return Real()
class Real:
    def run(self):
        pass
class Made(Factory):
    def run(self):
        pass
class Plain(Allocating):
    def run(self):
        pass
def made():
    Made().run()
def plain():
    Plain().run()
