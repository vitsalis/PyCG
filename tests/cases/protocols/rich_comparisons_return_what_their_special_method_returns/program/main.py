
def target(): pass
def other(): pass
def reflected(): pass
class C:
    def __eq__(self, o):
        return target
    def __lt__(self, o):
        return other
class D:
    def __gt__(self, o):
        return reflected
def use():
    (C() == 1)()
    (C() < C() < C())()
    (1 < D())()
