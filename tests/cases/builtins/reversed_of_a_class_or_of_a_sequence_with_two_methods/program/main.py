
import sys
class A:
    pass
class B:
    if sys.argv:
        def __len__(self): return 1
        def __getitem__(self, i): pass
    else:
        def __len__(self): return 2
        def __getitem__(self, i): pass
def run():
    reversed(A)
    reversed(B())
