
class Itself:
    def __init__(self): self.left = 3
    def __iter__(self): return self
    def __next__(self):
        if self.left == 0:
            raise StopIteration
        self.left -= 1
        return 1
    def __len__(self): return self.left
class Outer:
    def __iter__(self): return Itself()
    def __len__(self): return 3

def itself(x):
    a, *b = x
def other(x):
    a, *b = x
itself(Itself())
other(Outer())
