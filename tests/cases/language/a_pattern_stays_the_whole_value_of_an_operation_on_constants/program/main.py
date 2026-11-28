
import ext
def f(): pass
def g(): pass

table = {"pre_a": f, "other": g}
def read(name):
    table["pre_" + name]()
    table["pre_%s" % name]()
read("a")
