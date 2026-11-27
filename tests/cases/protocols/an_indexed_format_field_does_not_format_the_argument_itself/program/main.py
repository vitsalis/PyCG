
class A:
    def __format__(self, spec): return ""
"{0[k]}".format(A())
