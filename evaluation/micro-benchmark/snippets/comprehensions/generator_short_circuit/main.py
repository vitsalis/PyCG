def func1():
    return True

def func2():
    return False

results = (f() for f in (func1, func2))
found = any(results)
