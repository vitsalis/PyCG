
class A:
    def m(self): pass
class B:
    def m(self): pass
def whole(x, classes):
    ts = tuple(classes)
    if isinstance(x, ts):
        x.m()
def nested(x, classes):
    if isinstance(x, (A, tuple(classes))):
        x.m()
def twice(x):
    if isinstance(x, ((A, A),)):
        x.m()
for test in (whole, nested):
    test(A(), [A])
    test(B(), [A])
twice(A())
twice(B())
