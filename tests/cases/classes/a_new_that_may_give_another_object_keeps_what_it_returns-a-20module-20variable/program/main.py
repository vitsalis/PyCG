
import ext
def f(): pass
def g(): pass


def keep(function):
    return function

class Base:

    def __new__(cls, *args):
        global cached
        cached = object.__new__(Loud)
        return cached

class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
Quiet().speak()
