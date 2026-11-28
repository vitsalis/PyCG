
class Flag:
    def __bool__(self): return False
    def __len__(self): return 1
class Queue:
    def __len__(self): return 0
def branch(f):
    if f:
        pass
def loop(q):
    while q:
        break
def negate(f):
    return not f
def operands(f, q):
    return f and q
def arm(q):
    return 1 if q else 2
def check(q):
    assert q
def keep(f):
    return [i for i in [1] if f]
for f, q in [(Flag(), Queue())]:
    branch(f)
    loop(q)
    negate(f)
    operands(f, q)
    arm(q)
    check(q)
    keep(f)
