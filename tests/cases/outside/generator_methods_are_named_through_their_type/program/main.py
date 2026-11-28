
def worker():
    yield 1
g = worker()
g.send(None)
g.close()
