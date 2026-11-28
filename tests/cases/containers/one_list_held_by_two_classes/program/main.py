def f(): pass
def g(): pass
def h(): pass

L = [f]
class A:
    x = L
class B:
    x = L
A.x[0]()
B.x[0]()
