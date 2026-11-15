def func1():
    pass

def func2():
    pass

def register(f, registry=[]):
    registry.append(f)
    return registry

register(func1)
for f in register(func2):
    f()
