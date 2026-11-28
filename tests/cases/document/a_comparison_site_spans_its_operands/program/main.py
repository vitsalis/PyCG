class C:
    def __lt__(self, other): return D()
    def __contains__(self, item): return True
class D:
    def __bool__(self): return True
a, b, c = C(), C(), C()
a < b < c
1 in a
