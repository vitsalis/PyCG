
import ext
def f(): pass
def g(): pass


class Base:

    def __new__(cls, *args, **kwargs):
        instance = super(Base, cls).__new__(cls)
        instance.ready = False
        return instance

class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
Quiet().speak()
