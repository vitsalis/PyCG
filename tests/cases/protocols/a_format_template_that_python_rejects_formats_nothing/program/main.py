
class A:
    def __format__(self, spec): return ""
"{".format(A())
