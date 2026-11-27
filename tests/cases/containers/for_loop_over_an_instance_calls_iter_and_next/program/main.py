
def f(): pass
class Items:
    def __iter__(self):
        return self
    def __next__(self):
        return f

def use(items):
    for item in items:
        item()
use(Items())
