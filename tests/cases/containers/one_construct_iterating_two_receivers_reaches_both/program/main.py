
def f(): pass
class It:
    def __iter__(self):
        return iter([f])
a = []
b = []
for target in (a, b):
    target.extend(It())
def use_a():
    a[0]()
def use_b():
    b[0]()
