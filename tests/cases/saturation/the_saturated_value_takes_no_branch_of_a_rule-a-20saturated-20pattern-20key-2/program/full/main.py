
def good(): pass
def bad(): pass
table = {"a.x": good, "b.x": good, "c.x": good, "extra": bad}
def use(name):
    for key in ("a.%s" % name, "b.%s" % name, "c.%s" % name):
        table[key]()
use("x")
