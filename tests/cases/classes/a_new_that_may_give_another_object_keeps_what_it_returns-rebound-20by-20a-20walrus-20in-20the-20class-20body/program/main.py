
import ext
def f(): pass
def g(): pass


def keep(function):
    return function

class Base:

    def __new__(cls, *args):
        return object.__new__(cls)
    keep(__new__ := lambda cls, *args: object.__new__(Loud))

class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
Quiet().speak()
