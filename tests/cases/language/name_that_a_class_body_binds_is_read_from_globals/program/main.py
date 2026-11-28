
def global_target(): pass
f = global_target
class C:
    f = f
C.f()
def outer():
    def local_target(): pass
    def lexical(): pass
    f = local_target
    class D:
        f = f
        f()
        lexical()
outer()
