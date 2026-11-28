
import ext
def f(): pass
def g(): pass

class Point:
    def __new__(cls, x):
        return super().__new__(cls)
    def __init__(self, x):
        pass
    def norm(self):
        pass
Point(1).norm()
