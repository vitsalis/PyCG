def f(): pass
def g(): pass
def h(): pass

def take(a):
    a()
items = [f]
items["a"]
take(*items)
