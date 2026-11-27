
import ext
def f(): pass
def g(): pass

class Base:
    @staticmethod
    def __new__(cls):
        return super().__new__(cls)
class Child(Base):
    def __init__(self):
        pass
def make():
    Child()
