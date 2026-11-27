
def f(): pass
class Items:
    def __iter__(self):
        return self
    def __next__(self):
        return f

def g(): pass
def use():
    next(iter(Items()))()
    next(iter([g]))()
