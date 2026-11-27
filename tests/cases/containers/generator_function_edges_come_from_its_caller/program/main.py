
def f(): pass
def produce():
    yield f
def consume(values):
    for value in values:
        value()
consume(produce())
