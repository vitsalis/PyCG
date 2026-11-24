def outer_source():
    return [1, 2]

def inner_source(x):
    return [x, x]

values = [y for x in outer_source() for y in inner_source(x)]
