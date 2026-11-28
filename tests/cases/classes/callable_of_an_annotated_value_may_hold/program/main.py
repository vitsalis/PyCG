
def f(): pass
def use(x: int):
    if callable(x):
        f()
