
import ext
def f(): pass
def g(): pass


class Base:

    @staticmethod
    def __new__(cls):
        return super().__new__(cls)

class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
Quiet().speak()
