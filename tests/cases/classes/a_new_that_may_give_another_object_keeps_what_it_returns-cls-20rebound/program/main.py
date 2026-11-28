
import ext
def f(): pass
def g(): pass


def keep(function):
    return function

class Base:

    def __new__(cls, *args):
        cls = Loud
        return object.__new__(cls)

class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
Quiet().speak()
