
def f(): pass
def g(): pass
def h(): pass

def run():
    handler = f
    {(handler := g): handler()}
