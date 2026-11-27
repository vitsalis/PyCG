
def f(): pass
def g(): pass
handlers = {"f": f}
handlers.get("f")()
sorted([g])[0]()
