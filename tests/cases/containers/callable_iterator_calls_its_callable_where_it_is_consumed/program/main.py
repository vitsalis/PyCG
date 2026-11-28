
def target(): pass
def callback():
    return target
def create():
    return iter(callback, None)
def consume(iterator):
    for value in iterator:
        value()
def step(iterator):
    return next(iterator)
consume(create())
step(create())
