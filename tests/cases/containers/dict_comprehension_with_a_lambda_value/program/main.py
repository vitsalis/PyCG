
def f(): pass
table = {name: (lambda: f()) for name in ("a",)}
table["a"]()
