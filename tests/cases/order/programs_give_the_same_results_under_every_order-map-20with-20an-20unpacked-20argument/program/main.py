
def f(): pass
def g(): pass
def second(a, b): return b
def run(*rest):
    for x in map(second, [f], *rest):
        x()
run([g], [f])
