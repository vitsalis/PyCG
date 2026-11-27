
def f(): pass
def g(): pass
def h(): pass
def k(): pass
def pair(*iterables):
    return zip(*iterables)
for first, second in zip([f], [g]):
    second()
for first, second in pair([h], [k]):
    first()
