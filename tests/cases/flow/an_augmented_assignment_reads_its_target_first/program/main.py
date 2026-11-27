
def f(): pass
def g(): pass
def h(): pass

class A:
    def __iadd__(self, other):
        return self
class B:
    def __iadd__(self, other):
        return self
def run():
    value = A()
    value += (value := B())
