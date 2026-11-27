
class Itself:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    def __len__(self): return 0
class Hinted:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    def __length_hint__(self): return 0
class Inner:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    def __len__(self): return 0
class Outer:
    def __iter__(self): return Inner()
    def __len__(self): return 0
class Builtin:
    def __iter__(self): return iter([])
    def __len__(self): return 0

def itself(x):
    b"".join(x)
def other(x):
    b"".join(x)
def builtin(x):
    b"".join(x)
itself(Itself())
itself(Hinted())
other(Outer())
builtin(Builtin())
