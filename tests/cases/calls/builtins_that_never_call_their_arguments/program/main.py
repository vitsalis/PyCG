
class C:
    def __call__(self): pass
def f(): pass
print(f, C())
isinstance(f, C)
callable(f)
id(f)
