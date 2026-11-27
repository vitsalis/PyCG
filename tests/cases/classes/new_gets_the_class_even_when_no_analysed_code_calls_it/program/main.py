
import ext
def f(): pass
def g(): pass

class Library:
    def __new__(cls):
        return cls()
    def __call__(self):
        pass
