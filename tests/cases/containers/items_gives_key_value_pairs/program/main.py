def f(): pass
def g(): pass
def h(): pass

for key, value in {f: g}.items():
    value()
