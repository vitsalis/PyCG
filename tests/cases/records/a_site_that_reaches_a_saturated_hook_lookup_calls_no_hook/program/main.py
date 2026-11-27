
class C:
    pass
def h1(self, name, value): pass
def h2(self, name, value): pass
def h3(self, name, value): pass
C.__setattr__ = h1
def early(c):
    c.a = 1
def late(c):
    c.b = 1
def s1(): return s2
def s2(): return s3
def s3(): return (h2, h3)
for hook in s1()()():
    C.__setattr__ = hook
def l1(): return l2
def l2(): return l3
def l3(): return l4
def l4(): return l5
def l5(): return late
c = C()
early(c)
l1()()()()()(c)
