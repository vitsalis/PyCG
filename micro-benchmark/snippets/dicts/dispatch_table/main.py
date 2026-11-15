def add(a, b):
    return a + b

def sub(a, b):
    return a - b

OPS = {"+": add, "-": sub}

def evaluate(op, a, b):
    return OPS[op](a, b)

evaluate("-", 3, 1)
