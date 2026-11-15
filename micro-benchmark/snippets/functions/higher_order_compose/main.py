def increment(x):
    return x + 1

def double(x):
    return x * 2

def compose(f, g):
    def composed(x):
        return f(g(x))
    return composed

compose(increment, double)(3)
