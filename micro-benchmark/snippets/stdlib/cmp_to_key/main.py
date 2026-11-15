import functools

def compare(a, b):
    return a - b

sorted([3, 1], key=functools.cmp_to_key(compare))
