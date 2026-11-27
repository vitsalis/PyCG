
@(lambda f: f)
def f(cb=lambda: 1):
    return lambda: 2
