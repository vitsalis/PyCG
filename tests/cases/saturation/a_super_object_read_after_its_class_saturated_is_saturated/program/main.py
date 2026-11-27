class B0:
    def run(self): pass
class B1:
    def run(self): pass
class B2:
    def run(self): pass
class B3:
    def run(self): pass
class B4:
    def run(self): pass
def c1_0(): return c1_1
def c1_1(): return c1_2
def c1_2(): return c1_3
def c1_3(): return c1_4
def c1_4(): return c1_5
def c1_5(): return c1_6
def c1_6(): return B1
def c2_0(): return c2_1
def c2_1(): return c2_2
def c2_2(): return c2_3
def c2_3(): return c2_4
def c2_4(): return c2_5
def c2_5(): return c2_6
def c2_6(): return B2
def c3_0(): return c3_1
def c3_1(): return c3_2
def c3_2(): return c3_3
def c3_3(): return c3_4
def c3_4(): return c3_5
def c3_5(): return c3_6
def c3_6(): return B3
def c4_0(): return c4_1
def c4_1(): return c4_2
def c4_2(): return c4_3
def c4_3(): return c4_4
def c4_4(): return c4_5
def c4_5(): return c4_6
def c4_6(): return B4
REG = [B0]
REG.append(c1_0()()()()()()())
REG.append(c2_0()()()()()()())
REG.append(c3_0()()()()()()())
REG.append(c4_0()()()()()()())
def pick():
    for b in REG:
        return b
HOLD = []
class D(pick()):
    def __init__(self):
        HOLD.append(super())
D()
def k0(): return k1
def k1(): return k2
def k2(): return k3
def k3(): return k4
def k4(): return k5
def k5(): return k6
def k6(): return k7
def k7(): return k8
def k8(): return k9
def k9(): return k10
def k10(): return k11
def k11(): return k12
def k12(): return k13
def k13(): return k14
def k14(): return identity
def identity(x): return x
def use():
    k0()()()()()()()()()()()()()()()(HOLD[0]).other()
use()
