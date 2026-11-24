def func1():
    pass

def apply[F](f: F) -> F:
    f()
    return f

apply(func1)
