
class C:
    def run(self): pass
def f(): pass
def g(): pass
name = ["run"][0]
getattr(C(), name)()
table = {"a": f, "b": g}
key = ["a"][0]
table[key]()
