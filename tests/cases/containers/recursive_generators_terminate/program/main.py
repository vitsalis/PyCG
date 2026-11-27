
def f(): pass
def walk(node):
    yield node
    yield from walk(node)
    for child in walk(f):
        yield child
for value in walk(f):
    value()
