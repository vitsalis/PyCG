def f(): pass
def g(): pass
def h(): pass
{'a': f}.get('b', g)()
