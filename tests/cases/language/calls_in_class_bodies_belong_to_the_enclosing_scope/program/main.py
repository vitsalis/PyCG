
def make(): pass
class C:
    value = make()
    key = lambda: make()
    class Inner:
        other = [make() for _ in range(2)]
def f():
    class D:
        value = make()
