
def f(): pass
def g(): pass
def h(): pass

last = h
[last := handler for handler in (f, g)]
last()
