
import ext
def f(): pass
def g(): pass

class Failure(Exception):
    def __init__(self):
        pass
    def describe(self):
        pass
Failure().describe()
