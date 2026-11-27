
def outer(f):
    def outer_wrapper():
        f()
    return outer_wrapper
def inner(f):
    def inner_wrapper():
        f()
    return inner_wrapper
@outer
@inner
def g(): pass
g()
