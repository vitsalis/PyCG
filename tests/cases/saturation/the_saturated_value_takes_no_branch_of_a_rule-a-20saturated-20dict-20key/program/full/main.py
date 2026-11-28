
def good(): pass
def bad(): pass
table = {"a": good, "b": good, "c": good, "extra": bad}
for key in ("a", "b", "c"):
    table[key]()
