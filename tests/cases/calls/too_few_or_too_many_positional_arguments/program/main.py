
def none(): pass
def one(a): pass
def optional(a, b=1): pass
def run(f):
    f(1)
for f in (none, one, optional):
    run(f)
def two(f):
    f(1, 2, 3)
two(optional)
