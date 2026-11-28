
def f(): pass
class Items:
    def __iter__(self):
        return self
    def __next__(self):
        return f

def comprehension(items):
    [x() for x in items]
def unpacking(items):
    first, *rest = items
    first()
def builtin(items):
    list(items)[0]()
comprehension(Items())
unpacking(Items())
builtin(Items())
