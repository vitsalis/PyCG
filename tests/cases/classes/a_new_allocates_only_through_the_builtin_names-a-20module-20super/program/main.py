
import ext
def f(): pass
def g(): pass


class Maker:
    def __new__(cls, *rest):
        return object.__new__(Loud)
def super(*args):
    return Maker

class Base:

    def __new__(cls, *args):
        return super().__new__(cls)

class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
Quiet().speak()
