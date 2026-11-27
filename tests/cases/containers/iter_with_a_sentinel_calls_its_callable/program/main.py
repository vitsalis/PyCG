
def target():
    return f
def f(): pass
class Reader:
    def read(self): return ""
def use():
    for value in iter(target, None):
        value()
    for chunk in iter(Reader().read, ""):
        pass
