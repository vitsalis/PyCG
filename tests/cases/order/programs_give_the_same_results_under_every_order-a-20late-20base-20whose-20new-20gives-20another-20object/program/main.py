
import sys
class Allocating:
    def __new__(cls):
        return super().__new__(cls)
class Factory:
    def __new__(cls):
        return Real()
class Real:
    def run(self): pass
def late():
    return Factory
Base = Allocating
if sys.argv:
    Base = late()
class Made(Base):
    def run(self): pass
class Loud(Allocating):
    def __getattr__(self, name): pass
class Quiet(Allocating):
    def run(self): pass
def made():
    Made().run()
def quiet():
    Loud()
    Quiet().run()
