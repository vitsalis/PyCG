
def f(): pass
def g(): pass
def h(): pass

def run():
    handler = f
    calls = (handler() for _ in range(1))
    handler = g
    list(calls)
