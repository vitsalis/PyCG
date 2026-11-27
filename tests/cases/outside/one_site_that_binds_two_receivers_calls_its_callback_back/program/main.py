
class First(classmethod): pass
class Second(classmethod): pass
def f(cls): pass
for kind in (First, Second):
    kind(f)
