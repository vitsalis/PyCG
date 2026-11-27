
def f(): pass
def g(): pass
def ident(value):
    locals()
    return value
def first():
    ident(f)()
def second():
    ident(g)()
