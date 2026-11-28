
import ext
def f(): pass
def g(): pass


def keep(function):
    return function

class Base:

    def __new__(cls, *args):
        instance = object.__new__(cls)
        if args:
            instance = Loud()
        return instance

class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
Quiet().speak()
