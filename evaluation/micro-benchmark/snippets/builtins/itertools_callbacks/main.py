import itertools

def multiply(a, b):
    return a * b

def small(n):
    return n < 3

def parity(n):
    return n % 2

list(itertools.starmap(multiply, [(1, 2), (3, 4)]))
list(itertools.takewhile(small, [1, 5, 2]))
list(itertools.groupby([1, 3, 2], key=parity))
