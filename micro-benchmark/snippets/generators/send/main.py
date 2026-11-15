def func1():
    return 1

def worker():
    result = None
    while True:
        task = yield result
        result = task()

g = worker()
next(g)
g.send(func1)
