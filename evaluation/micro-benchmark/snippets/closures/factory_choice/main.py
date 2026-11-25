def make(kind):
    def add(a, b):
        return a + b

    def sub(a, b):
        return a - b

    if kind == "add":
        return add
    return sub

op = make("sub")
op(3, 1)
