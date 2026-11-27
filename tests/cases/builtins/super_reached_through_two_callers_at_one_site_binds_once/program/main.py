
class P:
    def m(self): pass
class Q(P):
    pass
class A:
    __call__ = super
class B:
    __call__ = super
def run(q):
    for o in (A(), B()):
        o(Q, q).m()
run(Q())
