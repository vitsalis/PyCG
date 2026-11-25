def recover():
    pass

def gen():
    try:
        yield 1
    except ValueError:
        recover()
        yield 2

g = gen()
next(g)
g.throw(ValueError)
